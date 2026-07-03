"""feedback y satisfaccion

Revision ID: 20260702_0006
Revises: 20260617_0005
Create Date: 2026-07-02

Agrega:
    - tabla message_feedback (👍/👎 por mensaje)
    - columnas de satisfacción en conversations
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260702_0006"
down_revision = "20260617_0005"
branch_labels = None
depends_on = None


def upgrade():
    # ── Feedback por mensaje ────────────────────────────────────────────────
    op.create_table(
        "message_feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,server_default=sa.text("gen_random_uuid()")),
        sa.Column("message_id", postgresql.UUID(as_uuid=True),sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True),sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # "up" | "down"
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),server_default=sa.text("now()"), nullable=False),
    )
    # Restricción: un usuario solo puede calificar un mensaje una vez
    op.create_unique_constraint(
        "uq_message_feedback_user_message",
        "message_feedback",
        ["message_id", "user_id"],
    )

    # ── Satisfacción al cerrar conversación ────────────────────────────────
    op.add_column("conversations",
        sa.Column("satisfaction_score", sa.Integer, nullable=True))   # 1=Sí, 2=Parcial, 3=No
    op.add_column("conversations",
        sa.Column("satisfaction_comment", sa.Text, nullable=True))
    op.add_column("conversations",
        sa.Column("resolved_by_bot", sa.Boolean, nullable=True))
    op.add_column("conversations",
        sa.Column("satisfaction_given_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("conversations", "satisfaction_given_at")
    op.drop_column("conversations", "resolved_by_bot")
    op.drop_column("conversations", "satisfaction_comment")
    op.drop_column("conversations", "satisfaction_score")
    op.drop_constraint("uq_message_feedback_user_message", "message_feedback", type_="unique")
    op.drop_table("message_feedback")