"""ia_general_approval y incident_alerts

Revision ID: 20260702_0007
Revises: 20260702_0006
Create Date: 2026-07-02

Cambios:
1. Agrega columna source_type a web_knowledge_cache
   ("web_search" | "general_ai") para distinguir respuestas de búsqueda web
   vs respuestas del general_assistant_service, sin romper la UI de aprobación
   que ya existe.

2. Crea tabla incident_alerts para detección de incidentes masivos:
   cuando N usuarios reportan el mismo aplicativo en una ventana de tiempo,
   se registra una alerta y se muestra en el dashboard.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260702_0007"
down_revision = "20260702_0006"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. source_type en web_knowledge_cache ──────────────────────────────
    op.add_column(
        "web_knowledge_cache",
        sa.Column("source_type", sa.String(30), nullable=False,server_default="web_search"),
    )
    op.create_index(
        "ix_web_knowledge_cache_source_type",
        "web_knowledge_cache",
        ["source_type"],
    )

    # ── 2. incident_alerts ──────────────────────────────────────────────────
    op.create_table(
        "incident_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,server_default=sa.text("gen_random_uuid()")),

        # Aplicativo / portal afectado
        sa.Column("application_name", sa.String(255), nullable=True, index=True),
        sa.Column("app_or_url", sa.String(500), nullable=True),
        sa.Column("category", sa.String(80), nullable=True, index=True),

        # Severidad calculada automáticamente según affected_users_count
        # "low" | "medium" | "high" | "critical"
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),

        # Conteo de usuarios afectados y ventana de tiempo
        sa.Column("affected_users_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False,server_default=sa.text("now()")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False,server_default=sa.text("now()")),

        # Estado de la alerta: open | acknowledged | resolved
        sa.Column("status", sa.String(30), nullable=False,server_default="open", index=True),

        sa.Column("recommendation", sa.Text, nullable=True),

        # IDs de conversaciones que generaron la alerta (para trazabilidad)
        sa.Column("conversation_ids", postgresql.JSONB, nullable=True),

        sa.Column("acknowledged_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,server_default=sa.text("now()"), index=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,server_default=sa.text("now()")),
    )


def downgrade():
    op.drop_table("incident_alerts")
    op.drop_index("ix_web_knowledge_cache_source_type", "web_knowledge_cache")
    op.drop_column("web_knowledge_cache", "source_type")