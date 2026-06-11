"""
Alembic env.py — Migraciones de base de datos BOTIQ.
Usa URL sync (psycopg2) para Alembic, separada de la async de la app.
"""

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.config import settings
from app.db.session import Base

# Importar todos los modelos para que Alembic los detecte
from app.models.user import User                          # noqa
from app.models.conversation import Conversation, Message # noqa
from app.models.faq import FAQ                            # noqa
from app.models.server_log import ServerLog               # noqa

config = context.config

# URL sync para Alembic (psycopg2, no asyncpg)
sync_url = settings.DATABASE_URL
if "asyncpg" in sync_url:
    sync_url = sync_url.replace("+asyncpg", "")
if sync_url.startswith("postgresql+psycopg2://"):
    pass  # ya está bien
elif sync_url.startswith("postgresql://"):
    pass  # psycopg2 por defecto

config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
