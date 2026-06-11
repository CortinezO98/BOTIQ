import asyncio

from app.db.session import engine, Base

# Importar todos los modelos para que SQLAlchemy los registre
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.models.faq import FAQ
from app.models.server_log import ServerLog
from app.models.knowledge_gap import KnowledgeGap
from app.models.audit_log import AuditLog


async def init_db():
    print("Creando tablas de BOTIQ...")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Tablas creadas correctamente.")


if __name__ == "__main__":
    asyncio.run(init_db())