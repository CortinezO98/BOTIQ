"""conversation flow and application matrix

Revision ID: 20260617_0004
Revises: 20260617_0003
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260617_0004"
down_revision = "20260617_0003"
branch_labels = None
depends_on = None


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], unique: bool = False):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = [i["name"] for i in inspector.get_indexes(table_name)]
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "application_matrix" not in tables:
        op.create_table(
            "application_matrix",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("app_name", sa.String(length=255), nullable=False),
            sa.Column("portal_name", sa.String(length=255), nullable=True),
            sa.Column("url_pattern", sa.String(length=500), nullable=True),
            sa.Column("ip_address", sa.String(length=100), nullable=True),
            sa.Column("server_name", sa.String(length=255), nullable=True),
            sa.Column("environment", sa.String(length=80), nullable=True),
            sa.Column("criticality", sa.String(length=50), nullable=True),
            sa.Column("owner_area", sa.String(length=255), nullable=True),
            sa.Column("support_group", sa.String(length=255), nullable=True),
            sa.Column("status_source", sa.String(length=255), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    _create_index_if_missing("ix_application_matrix_app_name", "application_matrix", ["app_name"])
    _create_index_if_missing("ix_application_matrix_portal_name", "application_matrix", ["portal_name"])
    _create_index_if_missing("ix_application_matrix_url_pattern", "application_matrix", ["url_pattern"])
    _create_index_if_missing("ix_application_matrix_ip_address", "application_matrix", ["ip_address"])
    _create_index_if_missing("ix_application_matrix_server_name", "application_matrix", ["server_name"])
    _create_index_if_missing("ix_application_matrix_is_active", "application_matrix", ["is_active"])
    _create_index_if_missing("ix_application_matrix_created_at", "application_matrix", ["created_at"])


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "application_matrix" in tables:
        op.drop_table("application_matrix")
