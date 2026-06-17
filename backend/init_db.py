"""Inicialización rápida de la base de datos — SOLO PARA DESARROLLO.

En producción la fuente oficial del esquema es Alembic:
    alembic upgrade head
"""
import asyncio
from pathlib import Path

from app.db.session import Base, engine
from app.models.application_matrix import ApplicationMatrix  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.faq import FAQ  # noqa: F401
from app.models.knowledge_gap import KnowledgeGap  # noqa: F401
from app.models.knowledge_document import KnowledgeDocument  # noqa: F401
from app.models.network_user import NetworkUser  # noqa: F401
from app.models.server_log import ServerLog  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.web_knowledge_cache import WebKnowledgeCache  # noqa: F401


async def init_db():
    print("Creando tablas de BOTIQ (modo desarrollo)...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tablas creadas correctamente.")


def stamp_alembic_head():
    """Alinea la versión de Alembic con el esquema recién creado."""
    try:
        from alembic import command
        from alembic.config import Config

        ini_path = Path(__file__).resolve().parent / "alembic.ini"
        if not ini_path.exists():
            print("alembic.ini no encontrado — omitiendo stamp. Ejecuta manualmente: alembic stamp head")
            return

        config = Config(str(ini_path))
        command.stamp(config, "head")
        print("Alembic marcado en head (alembic stamp head).")
    except Exception as exc:  # noqa: BLE001
        print(f"No se pudo hacer alembic stamp head automáticamente: {exc}")
        print("Ejecuta manualmente: alembic stamp head")


if __name__ == "__main__":
    asyncio.run(init_db())
    stamp_alembic_head()


