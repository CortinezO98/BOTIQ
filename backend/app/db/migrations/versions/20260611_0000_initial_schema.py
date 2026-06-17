"""initial schema: users, conversations, messages, faqs, knowledge_gaps, audit_logs, server_logs

Migración inicial REAL de BOTIQ. Crea las tablas base desde cero en una BD limpia.
Es idempotente: si las tablas ya existen (BD creada con init_db.py), no hace nada,
lo que permite ejecutar `alembic upgrade head` sin DuplicateTable/DuplicateColumn.

Revision ID: 20260611_0000
Revises:
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260611_0000"
down_revision = None
branch_labels = None
depends_on = None

# Enums alineados con app/core/roles.py y app/models/conversation.py.
# Se declaran con create_type=False y se crean manualmente con checkfirst
# para que la migración sea segura en BDs donde init_db.py ya los creó.
userrole_enum = postgresql.ENUM(
    "EMPLOYEE", "SUPPORT_ENGINEER", "ADMIN", name="userrole", create_type=False
)
moduletype_enum = postgresql.ENUM(
    "EMPLOYEE", "SUPPORT_RAG", "SERVER_VALIDATION", name="moduletype", create_type=False
)
messagerole_enum = postgresql.ENUM(
    "USER", "ASSISTANT", "SYSTEM", name="messagerole", create_type=False
)


def _existing_tables() -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return set(inspector.get_table_names())


def upgrade():
    bind = op.get_bind()
    tables = _existing_tables()

    # Crear tipos enum solo si no existen (checkfirst evita DuplicateObject).
    userrole_enum.create(bind, checkfirst=True)
    moduletype_enum.create(bind, checkfirst=True)
    messagerole_enum.create(bind, checkfirst=True)

    if "users" not in tables:
        op.create_table(
            "users",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("email", sa.String(length=255), nullable=False),
            sa.Column("full_name", sa.String(length=255), nullable=False),
            sa.Column("hashed_password", sa.String(length=255), nullable=False),
            sa.Column("role", userrole_enum, nullable=False, server_default="EMPLOYEE"),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if "conversations" not in tables:
        # Solo columnas base. Las columnas de controles de chat, validación de
        # soporte, contexto técnico y Aranda las agregan 0001 y 0002.
        op.create_table(
            "conversations",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id"),
                nullable=False,
            ),
            sa.Column("module", moduletype_enum, nullable=False, server_default="EMPLOYEE"),
            sa.Column("session_id", sa.String(length=100), nullable=True),
            sa.Column(
                "escalated_to_aranda",
                sa.Boolean(),
                nullable=True,
                server_default=sa.false(),
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_conversations_session_id", "conversations", ["session_id"])

    if "messages" not in tables:
        op.create_table(
            "messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "conversation_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("conversations.id"),
                nullable=False,
            ),
            sa.Column("role", messagerole_enum, nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("has_image", sa.Boolean(), nullable=True, server_default=sa.false()),
            sa.Column("image_gcs_url", sa.String(length=500), nullable=True),
            sa.Column("tokens_used", sa.Float(), nullable=True),
            sa.Column("response_time_ms", sa.Float(), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )

    if "faqs" not in tables:
        op.create_table(
            "faqs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=100), nullable=True),
            sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("hit_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_faqs_category", "faqs", ["category"])

    if "knowledge_gaps" not in tables:
        op.create_table(
            "knowledge_gaps",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("query", sa.String(length=255), nullable=False),
            sa.Column("module", sa.String(length=50), nullable=False),
            sa.Column("user_role", sa.String(length=50), nullable=False),
            sa.Column("frequency", sa.Integer(), nullable=True, server_default="1"),
            sa.Column("avg_confidence", sa.Float(), nullable=True, server_default="0"),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=True, server_default="open"),
            sa.Column("suggested_document", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_knowledge_gaps_query", "knowledge_gaps", ["query"])

    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("module", sa.String(length=50), nullable=True),
            sa.Column("ip_address", sa.String(length=50), nullable=True),
            sa.Column("user_agent", sa.String(length=255), nullable=True),
            sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
        op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
        op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    if "server_logs" not in tables:
        op.create_table(
            "server_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("server_name", sa.String(length=255), nullable=False),
            sa.Column("status", sa.String(length=50), nullable=False),
            sa.Column("memory_usage", sa.Float(), nullable=True),
            sa.Column("cpu_usage", sa.Float(), nullable=True),
            sa.Column("disk_usage", sa.Float(), nullable=True),
            sa.Column("is_healthy", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("raw_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("queried_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_server_logs_server_name", "server_logs", ["server_name"])


def downgrade():
    bind = op.get_bind()
    tables = _existing_tables()

    for table in ["server_logs", "audit_logs", "knowledge_gaps", "faqs", "messages", "conversations", "users"]:
        if table in tables:
            op.drop_table(table)

    messagerole_enum.drop(bind, checkfirst=True)
    moduletype_enum.drop(bind, checkfirst=True)
    userrole_enum.drop(bind, checkfirst=True)


