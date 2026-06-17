"""botiq flow aranda and application status controls

Revision ID: 20260611_0002
Revises: 20260611_0001
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260611_0002"
down_revision = "20260611_0001"
branch_labels = None
depends_on = None


def _add_column_if_missing(table_name: str, column: sa.Column):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    if column.name not in columns:
        op.add_column(table_name, column)


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [i["name"] for i in inspector.get_indexes(table_name)]
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    _add_column_if_missing("conversations", sa.Column("resolution_attempts", sa.Integer(), nullable=True, server_default="0"))
    _add_column_if_missing("conversations", sa.Column("ticket_eligible", sa.Boolean(), nullable=True, server_default=sa.false()))
    _add_column_if_missing("conversations", sa.Column("detected_url", sa.String(length=500), nullable=True))
    _add_column_if_missing("conversations", sa.Column("detected_ip", sa.String(length=100), nullable=True))
    _add_column_if_missing("conversations", sa.Column("application_status_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    _add_column_if_missing("conversations", sa.Column("aranda_ticket_id", sa.String(length=150), nullable=True))
    _add_column_if_missing("conversations", sa.Column("aranda_ticket_status", sa.String(length=100), nullable=True))
    _add_column_if_missing("conversations", sa.Column("aranda_ticket_created_at", sa.DateTime(timezone=True), nullable=True))

    _create_index_if_missing("ix_conversations_aranda_ticket_id", "conversations", ["aranda_ticket_id"])
    _create_index_if_missing("ix_conversations_detected_url", "conversations", ["detected_url"])
    _create_index_if_missing("ix_conversations_ticket_eligible", "conversations", ["ticket_eligible"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [i["name"] for i in inspector.get_indexes("conversations")]
    for idx in ["ix_conversations_ticket_eligible", "ix_conversations_detected_url", "ix_conversations_aranda_ticket_id"]:
        if idx in indexes:
            op.drop_index(idx, table_name="conversations")

    columns = [c["name"] for c in inspector.get_columns("conversations")]
    for col in [
        "aranda_ticket_created_at",
        "aranda_ticket_status",
        "aranda_ticket_id",
        "application_status_snapshot",
        "detected_ip",
        "detected_url",
        "ticket_eligible",
        "resolution_attempts",
    ]:
        if col in columns:
            op.drop_column("conversations", col)


