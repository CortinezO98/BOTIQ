import asyncio
import getpass

from sqlalchemy import select

from app.db.session import AsyncSessionLocal

# IMPORTANTE:
# Importar todos los modelos relacionados para que SQLAlchemy registre las relaciones.
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.models.faq import FAQ
from app.models.server_log import ServerLog
from app.models.knowledge_gap import KnowledgeGap
from app.models.audit_log import AuditLog

from app.core.security import hash_password
from app.core.roles import UserRole


async def main():
    print("=== Crear primer usuario administrador BOTIQ ===")

    email = input("Email admin: ").strip().lower()
    full_name = input("Nombre completo: ").strip()
    password = getpass.getpass("Contraseña: ").strip()
    confirm = getpass.getpass("Confirmar contraseña: ").strip()

    if not email or not full_name or not password:
        print("Todos los campos son obligatorios.")
        return

    if password != confirm:
        print("Las contraseñas no coinciden.")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.full_name = full_name
            user.hashed_password = hash_password(password)
            user.role = UserRole.ADMIN
            user.is_active = True

            await db.commit()
            print(f"Usuario existente actualizado como ADMIN: {email}")
            return

        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
            is_active=True,
        )

        db.add(user)
        await db.commit()

        print(f"Admin creado correctamente: {email}")


if __name__ == "__main__":
    asyncio.run(main())