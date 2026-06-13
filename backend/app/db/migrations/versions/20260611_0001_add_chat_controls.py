"""add chat controls, network users and conversation logs

Reescrita para ser idempotente: agrega columnas/índices/tablas solo si no
existen. Esto permite ejecutarla tanto sobre una BD creada por la migración
inicial 20260611_0000 (flujo normal de producción) como sobre una BD creada
con init_db.py en desarrollo, sin DuplicateColumn ni UndefinedTable.

Revision ID: 20260611_0001
Revises: 20260611_0000
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260611_0001"
down_revision = "20260611_0000"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _add_column_if_missing(table_name: str, column: sa.Column):
    columns = [c["name"] for c in _inspector().get_columns(table_name)]
    if column.name not in columns:
        op.add_column(table_name, column)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False):
    indexes = [i["name"] for i in _inspector().get_indexes(table_name)]
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    inspector = _inspector()
    tables = set(inspector.get_table_names())

    # --- Controles de flujo, consumo y validación en conversations ---
    _add_column_if_missing("conversations", sa.Column("selected_profile", sa.String(length=50), nullable=True))
    _add_column_if_missing("conversations", sa.Column("session_status", sa.String(length=30), nullable=True, server_default="active"))
    _add_column_if_missing("conversations", sa.Column("ended_reason", sa.String(length=255), nullable=True))
    _add_column_if_missing("conversations", sa.Column("question_count", sa.Integer(), nullable=True, server_default="0"))
    _add_column_if_missing("conversations", sa.Column("out_of_scope_count", sa.Integer(), nullable=True, server_default="0"))
    _add_column_if_missing("conversations", sa.Column("support_network_username", sa.String(length=150), nullable=True))
    _add_column_if_missing("conversations", sa.Column("support_network_validated", sa.Boolean(), nullable=True, server_default=sa.false()))
    _add_column_if_missing("conversations", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    _create_index_if_missing("ix_conversations_selected_profile", "conversations", ["selected_profile"])
    _create_index_if_missing("ix_conversations_session_status", "conversations", ["session_status"])
    _create_index_if_missing("ix_conversations_support_network_username", "conversations", ["support_network_username"])
    _create_index_if_missing("ix_conversations_created_at", "conversations", ["created_at"])
    _create_index_if_missing("ix_messages_created_at", "messages", ["created_at"])

    # --- Tabla de usuarios de red para validar ingenieros de soporte ---
    if "network_users" not in tables:
        op.create_table(
            "network_users",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("network_username", sa.String(length=150), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("full_name", sa.String(length=255), nullable=True),
            sa.Column("is_support_enabled", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing("ix_network_users_network_username", "network_users", ["network_username"], unique=True)
    _create_index_if_missing("ix_network_users_email", "network_users", ["email"], unique=True)
    _create_index_if_missing("ix_network_users_is_support_enabled", "network_users", ["is_support_enabled"])
    _create_index_if_missing("ix_network_users_is_active", "network_users", ["is_active"])
    _create_index_if_missing("ix_network_users_created_at", "network_users", ["created_at"])


def downgrade():
    inspector = _inspector()
    tables = set(inspector.get_table_names())

    if "network_users" in tables:
        op.drop_table("network_users")

    conv_indexes = [i["name"] for i in inspector.get_indexes("conversations")]
    for idx in [
        "ix_conversations_support_network_username",
        "ix_conversations_session_status",
        "ix_conversations_selected_profile",
        "ix_conversations_created_at",
    ]:
        if idx in conv_indexes:
            op.drop_index(idx, table_name="conversations")

    msg_indexes = [i["name"] for i in inspector.get_indexes("messages")]
    if "ix_messages_created_at" in msg_indexes:
        op.drop_index("ix_messages_created_at", table_name="messages")

    conv_columns = [c["name"] for c in inspector.get_columns("conversations")]
    for col in [
        "metadata",
        "support_network_validated",
        "support_network_username",
        "out_of_scope_count",
        "question_count",
        "ended_reason",
        "session_status",
        "selected_profile",
    ]:
        if col in conv_columns:
            op.drop_column("conversations", col)
