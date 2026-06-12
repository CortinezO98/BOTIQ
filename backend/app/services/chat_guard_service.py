from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.roles import UserRole
from app.models.conversation import Conversation
from app.models.network_user import NetworkUser
from app.models.user import User


class ChatGuardResult:
    def __init__(self, allowed: bool, reason: Optional[str] = None,
                 final_message: Optional[str] = None, end_session: bool = False,
                 status: str = "active"):
        self.allowed = allowed
        self.reason = reason
        self.final_message = final_message
        self.end_session = end_session
        self.status = status


class ChatGuardService:
    def is_business_related(self, text: str) -> bool:
        msg = (text or "").lower().strip()
        if not msg:
            return False
        if any(keyword in msg for keyword in settings.get_out_of_scope_keywords()):
            return False
        if any(keyword in msg for keyword in settings.get_business_keywords()):
            return True
        if msg in {"hola", "buenas", "buenos dias", "buenos días", "ayuda", "soporte", "gracias"}:
            return True
        return True

    async def validate_support_network_user(
        self,
        db: AsyncSession,
        current_user: User,
        network_username: Optional[str],
    ) -> tuple[bool, Optional[str]]:
        if current_user.role not in {UserRole.SUPPORT_ENGINEER, UserRole.ADMIN}:
            return False, "Tu usuario no tiene rol de Ingeniero de Soporte."

        if not settings.REQUIRE_SUPPORT_NETWORK_VALIDATION:
            return True, None

        value = (network_username or "").strip().lower()
        if not value:
            return False, "Debes ingresar tu usuario de red para usar el perfil de soporte."

        result = await db.execute(
            select(NetworkUser).where(
                NetworkUser.network_username == value,
                NetworkUser.is_active == True,
                NetworkUser.is_support_enabled == True,
            )
        )
        network_user = result.scalar_one_or_none()
        if network_user:
            return True, None

        allowed_domains = settings.get_support_allowed_domains()
        email = (current_user.email or "").lower()
        email_user = email.split("@")[0] if "@" in email else email
        email_domain = email.split("@")[1] if "@" in email else ""
        if email_domain in allowed_domains and value in {email_user, email}:
            return True, None

        return False, "Usuario de red no autorizado para el perfil de soporte."

    def evaluate_message(self, conversation: Conversation, message: str) -> ChatGuardResult:
        if conversation.session_status != "active":
            return ChatGuardResult(
                False,
                conversation.ended_reason or "session_already_ended",
                "Esta sesión ya fue finalizada. Inicia una nueva conversación para continuar.",
                True,
                conversation.session_status,
            )

        if len(message or "") > settings.MAX_MESSAGE_LENGTH:
            return ChatGuardResult(
                False,
                "message_too_long",
                f"Tu mensaje supera el límite permitido de {settings.MAX_MESSAGE_LENGTH} caracteres. Resume la consulta y vuelve a intentarlo.",
            )

        if (conversation.question_count or 0) >= settings.MAX_QUESTIONS_PER_SESSION:
            return ChatGuardResult(
                False,
                "question_limit_reached",
                f"Has alcanzado el límite de {settings.MAX_QUESTIONS_PER_SESSION} preguntas para esta sesión. Por control de consumo de IA, finalicé esta conversación.",
                True,
                "ended",
            )

        if not self.is_business_related(message):
            if (conversation.out_of_scope_count or 0) >= settings.MAX_OUT_OF_SCOPE_PER_SESSION:
                return ChatGuardResult(
                    False,
                    "out_of_scope_limit_reached",
                    "La consulta no está relacionada con servicios corporativos de soporte, conocimiento o infraestructura. Por política de uso adecuado de IA, finalicé esta sesión.",
                    True,
                    "blocked",
                )
            return ChatGuardResult(
                False,
                "out_of_scope_warning",
                "Tu consulta parece estar fuera del alcance corporativo de BOTIQ. Puedo ayudarte con accesos, sistemas internos, soporte técnico, documentación, servidores o procedimientos de TI.",
            )

        return ChatGuardResult(True)

    def finish_conversation(self, conversation: Conversation, reason: str, status: str = "ended"):
        conversation.session_status = status
        conversation.ended_reason = reason
        conversation.ended_at = datetime.now(timezone.utc)


chat_guard_service = ChatGuardService()
