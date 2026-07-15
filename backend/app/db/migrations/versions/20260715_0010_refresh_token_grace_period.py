"""refresh_token_grace_period

Revision ID: 20260715_0010
Revises: 20260715_0009
Create Date: 2026-07-15

Separa "el token ya se usó para rotar" (rotated_at, con período de gracia)
de "el token está revocado de verdad" (revoked_at, inmediato). Sin esto,
peticiones concurrentes con la cookie de refresh todavía no actualizada
(varias pestañas, o varias llamadas paralelas del frontend) quedaban en
cascada de 401 apenas la primera rotaba el token con éxito.
"""
from alembic import op
import sqlalchemy as sa

revision = "20260715_0010"
down_revision = "20260715_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "refresh_tokens",
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("refresh_tokens", "rotated_at")