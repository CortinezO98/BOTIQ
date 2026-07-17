"""server_knowledge_documents para la base de conocimiento de servidores

Crea la tabla que registra cada documento de Google Drive indexado en la
base de conocimiento de SERVIDORES (memoria/RAM, estado) -- completamente
separada de knowledge_documents (soporte general). Idempotente: si la tabla
ya existe, no hace nada.

Revision ID: 20260717_0011
Revises: 20260715_0010
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260717_0011"
down_revision = "20260715_0010"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "server_knowledge_documents" not in tables:
        op.create_table(
            "server_knowledge_documents",
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
        op.create_index(
            "ix_server_knowledge_documents_file_id",
            "server_knowledge_documents",
            ["file_id"],
            unique=True,
        )
        op.create_index(
            "ix_server_knowledge_documents_content_hash",
            "server_knowledge_documents",
            ["content_hash"],
        )
        op.create_index(
            "ix_server_knowledge_documents_status",
            "server_knowledge_documents",
            ["status"],
        )


def downgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "server_knowledge_documents" in tables:
        op.drop_table("server_knowledge_documents")