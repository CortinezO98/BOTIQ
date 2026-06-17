"""web knowledge cache suggestions

Revision ID: 20260617_0005
Revises: 20260617_0004
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260617_0005"
down_revision = "20260617_0004"
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
    tables = set(sa.inspect(bind).get_table_names())

    if "web_knowledge_cache" not in tables:
        op.create_table(
            "web_knowledge_cache",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("normalized_question", sa.String(length=500), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("category", sa.String(length=120), nullable=True),
            sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True, server_default="0"),
            sa.Column("status", sa.String(length=30), nullable=True, server_default="pending"),
            sa.Column("web_search_used", sa.Boolean(), nullable=True, server_default=sa.true()),
            sa.Column("usage_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejected_by", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("faq_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    _create_index_if_missing("ix_web_knowledge_cache_normalized_question", "web_knowledge_cache", ["normalized_question"])
    _create_index_if_missing("ix_web_knowledge_cache_category", "web_knowledge_cache", ["category"])
    _create_index_if_missing("ix_web_knowledge_cache_status", "web_knowledge_cache", ["status"])
    _create_index_if_missing("ix_web_knowledge_cache_created_by", "web_knowledge_cache", ["created_by"])
    _create_index_if_missing("ix_web_knowledge_cache_created_at", "web_knowledge_cache", ["created_at"])
    _create_index_if_missing("ix_web_knowledge_cache_expires_at", "web_knowledge_cache", ["expires_at"])
    _create_index_if_missing("ix_web_knowledge_cache_faq_id", "web_knowledge_cache", ["faq_id"])


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "web_knowledge_cache" in tables:
        op.drop_table("web_knowledge_cache")
