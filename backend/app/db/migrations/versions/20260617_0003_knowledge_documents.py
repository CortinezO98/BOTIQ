"""knowledge_documents para RAG incremental y estado por documento

Crea la tabla que registra cada documento de Google Drive indexado en el RAG:
estado, número de chunks, hash de contenido y fechas. Idempotente: si la tabla
ya existe (p. ej. creada por init_db.py en desarrollo), no hace nada.

Revision ID: 20260617_0003
Revises: 20260611_0002
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260617_0003"
down_revision = "20260611_0002"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "knowledge_documents" not in tables:
        op.create_table(
            "knowledge_documents",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("file_id", sa.String(length=255), nullable=False),
            sa.Column("file_name", sa.String(length=500), nullable=False),
            sa.Column("doc_type", sa.String(length=50), nullable=True),
            sa.Column("mime_type", sa.String(length=255), nullable=True),
            sa.Column("drive_modified_at", sa.String(length=100), nullable=True),
            sa.Column("content_hash", sa.String(length=64), nullable=True),
            sa.Column("chunk_count", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("status", sa.String(length=30), nullable=True, server_default="pending"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_knowledge_documents_file_id", "knowledge_documents", ["file_id"], unique=True)
        op.create_index("ix_knowledge_documents_content_hash", "knowledge_documents", ["content_hash"])
        op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "knowledge_documents" in tables:
        op.drop_table("knowledge_documents")
