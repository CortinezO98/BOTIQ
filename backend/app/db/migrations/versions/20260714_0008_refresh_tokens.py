"""refresh_tokens

Revision ID: 20260714_0008
Revises: 20260702_0007
Create Date: 2026-07-14

Soporte de sesión con refresh token (login persistente por cookie httpOnly):
- Tabla refresh_tokens: guarda el HASH del refresh token (nunca el valor real),
  con expiración, revocación y user_agent para trazabilidad básica.
- Permite revocar sesiones individuales (logout) y rotación en cada /auth/refresh.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260714_0008"
down_revision = "20260702_0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("user_agent", sa.String(500), nullable=True),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)


def downgrade():
    op.drop_index("ix_refresh_tokens_token_hash", "refresh_tokens")
    op.drop_index("ix_refresh_tokens_user_id", "refresh_tokens")
    op.drop_table("refresh_tokens")