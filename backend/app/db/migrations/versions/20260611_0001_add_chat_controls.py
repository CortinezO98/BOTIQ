"""add chat controls, network users and conversation logs

Revision ID: 20260611_0001
Revises:
Create Date: 2026-06-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260611_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("conversations", sa.Column("selected_profile", sa.String(length=50), nullable=True))
    op.add_column("conversations", sa.Column("session_status", sa.String(length=30), nullable=True, server_default="active"))
    op.add_column("conversations", sa.Column("ended_reason", sa.String(length=255), nullable=True))
    op.add_column("conversations", sa.Column("question_count", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("conversations", sa.Column("out_of_scope_count", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("conversations", sa.Column("support_network_username", sa.String(length=150), nullable=True))
    op.add_column("conversations", sa.Column("support_network_validated", sa.Boolean(), nullable=True, server_default=sa.false()))
    op.add_column("conversations", sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_index("ix_conversations_selected_profile", "conversations", ["selected_profile"])
    op.create_index("ix_conversations_session_status", "conversations", ["session_status"])
    op.create_index("ix_conversations_support_network_username", "conversations", ["support_network_username"])
    op.create_index("ix_conversations_created_at", "conversations", ["created_at"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])

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
    op.create_index("ix_network_users_network_username", "network_users", ["network_username"], unique=True)
    op.create_index("ix_network_users_email", "network_users", ["email"], unique=True)
    op.create_index("ix_network_users_is_support_enabled", "network_users", ["is_support_enabled"])
    op.create_index("ix_network_users_is_active", "network_users", ["is_active"])
    op.create_index("ix_network_users_created_at", "network_users", ["created_at"])


def downgrade():
    op.drop_index("ix_network_users_created_at", table_name="network_users")
    op.drop_index("ix_network_users_is_active", table_name="network_users")
    op.drop_index("ix_network_users_is_support_enabled", table_name="network_users")
    op.drop_index("ix_network_users_email", table_name="network_users")
    op.drop_index("ix_network_users_network_username", table_name="network_users")
    op.drop_table("network_users")

    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_conversations_created_at", table_name="conversations")
    op.drop_index("ix_conversations_support_network_username", table_name="conversations")
    op.drop_index("ix_conversations_session_status", table_name="conversations")
    op.drop_index("ix_conversations_selected_profile", table_name="conversations")

    op.drop_column("conversations", "metadata")
    op.drop_column("conversations", "support_network_validated")
    op.drop_column("conversations", "support_network_username")
    op.drop_column("conversations", "out_of_scope_count")
    op.drop_column("conversations", "question_count")
    op.drop_column("conversations", "ended_reason")
    op.drop_column("conversations", "session_status")
    op.drop_column("conversations", "selected_profile")
