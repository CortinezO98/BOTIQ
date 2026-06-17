from datetime import datetime, timezone
from typing import Any, Dict, Optional
import time

import httpx

from app.core.config import settings
from app.models.conversation import Conversation
from app.models.user import User


class ArandaService:
    """
    Servicio de integración con Aranda.

    BOTIQ solo debe crear tickets como última instancia, después de:
    1. Validar alcance del negocio.
    2. Revisar FAQs/base de conocimiento.
    3. Consultar estado de URL/IP/aplicativo si aplica.
    4. Agotar las validaciones mínimas configuradas.
    """

    def is_configured(self) -> bool:
        return bool(settings.ARANDA_API_URL and settings.ARANDA_API_KEY)

    async def create_ticket(
        self,
        conversation: Conversation,
        current_user: User,
        subject: str,
        description: str,
        application_status: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.is_configured():
            demo_id = f"BOTIQ-PENDING-{str(conversation.id)[:8]}"
            return {
                "created": False,
                "pending_configuration": True,
                "ticket_id": demo_id,
                "status": "pending_aranda_configuration",
                "message": "Aranda no está configurado. El caso queda marcado como elegible para ticket.",
            }

        payload = {
            "subject": subject[:180],
            "description": description,
            "requester": {
                "email": current_user.email,
                "full_name": current_user.full_name,
                "user_id": str(current_user.id),
            },
            "metadata": {
                "source": "BOTIQ",
                "conversation_id": str(conversation.id),
                "session_id": conversation.session_id,
                "selected_profile": conversation.selected_profile,
                "question_count": conversation.question_count,
                "resolution_attempts": conversation.resolution_attempts,
                "detected_url": conversation.detected_url,
                "detected_ip": conversation.detected_ip,
                "application_status": application_status or conversation.application_status_snapshot,
            },
        }

        if settings.ARANDA_PROJECT_ID:
            payload["project_id"] = settings.ARANDA_PROJECT_ID
        if settings.ARANDA_CATEGORY_ID:
            payload["category_id"] = settings.ARANDA_CATEGORY_ID
        if settings.ARANDA_SERVICE_ID:
            payload["service_id"] = settings.ARANDA_SERVICE_ID

        headers = {
            "Authorization": f"Bearer {settings.ARANDA_API_KEY}",
            "Content-Type": "application/json",
        }

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=settings.ARANDA_TIMEOUT_SECONDS) as client:
                response = await client.post(settings.ARANDA_API_URL.rstrip("/") + "/tickets", json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()

            ticket_id = str(data.get("id") or data.get("ticket_id") or data.get("case_id") or "")
            status = str(data.get("status") or "created")

            return {
                "created": True,
                "ticket_id": ticket_id,
                "status": status,
                "raw": data,
                "response_time_ms": round((time.time() - start) * 1000, 2),
                "message": f"Ticket creado correctamente en Aranda: {ticket_id}",
            }
        except Exception as exc:
            return {
                "created": False,
                "ticket_id": None,
                "status": "error",
                "message": f"No fue posible crear el ticket en Aranda: {exc}",
            }

    def build_ticket_description(self, conversation: Conversation, last_user_message: str) -> str:
        return (
            "Caso generado desde BOTIQ.\n\n"
            f"Usuario perfil seleccionado: {conversation.selected_profile}\n"
            f"Sesión: {conversation.session_id}\n"
            f"Conversación: {conversation.id}\n"
            f"Preguntas realizadas: {conversation.question_count}\n"
            f"Intentos de solución: {conversation.resolution_attempts}\n"
            f"URL detectada: {conversation.detected_url or 'No registrada'}\n"
            f"IP detectada: {conversation.detected_ip or 'No registrada'}\n"
            f"Estado aplicativo: {conversation.application_status_snapshot or 'No disponible'}\n\n"
            f"Última solicitud del usuario:\n{last_user_message}"
        )

    def mark_ticket_result(self, conversation: Conversation, result: Dict[str, Any]):
        if result.get("ticket_id"):
            conversation.aranda_ticket_id = str(result["ticket_id"])
        conversation.aranda_ticket_status = str(result.get("status") or "")
        conversation.aranda_ticket_created_at = datetime.now(timezone.utc)
        conversation.escalated_to_aranda = bool(result.get("created"))


aranda_service = ArandaService()


