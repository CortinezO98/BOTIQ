"""mfa_totp

Revision ID: 20260715_0009
Revises: 20260714_0008
Create Date: 2026-07-15

Agrega soporte de MFA (TOTP) para usuarios, pensado en primera instancia
para el rol admin:
- mfa_enabled: si está activo, /auth/login exige un segundo factor.
- mfa_secret_encrypted: secreto TOTP cifrado con Fernet (nunca en texto
  plano). Con mfa_enabled=False y este campo no nulo, significa
  "enrolamiento generado, pendiente de confirmar con un código válido".
- mfa_enrolled_at: fecha en que se confirmó el enrolamiento.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260715_0009"
down_revision = "20260714_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("mfa_secret_encrypted", sa.String(255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("users", "mfa_enrolled_at")
    op.drop_column("users", "mfa_secret_encrypted")
    op.drop_column("users", "mfa_enabled")