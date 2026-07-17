"""
incident_service.py — Detección automática de incidentes masivos.

Lógica central:
- Cada vez que un usuario reporta un aplicativo/URL/portal como caído o con errores,
    se llama a check_and_create_alert().
- Si en los últimos INCIDENT_WINDOW_MINUTES ya hubo INCIDENT_THRESHOLD reportes
    distintos del mismo aplicativo, se crea o actualiza una alerta de incidente.
- Las alertas abiertas se muestran en el dashboard de admin con badge de urgencia.

Configuración (vía settings o constantes):
    INCIDENT_THRESHOLD        = 5   usuarios distintos
    INCIDENT_WINDOW_MINUTES   = 15  minutos de ventana
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.incident_alert import IncidentAlert
from app.core.logging_config import get_logger

logger = get_logger(__name__, service="incident_detection")

INCIDENT_THRESHOLD = 5        # usuarios distintos en la ventana
INCIDENT_WINDOW_MINUTES = 15  # ventana de tiempo en minutos


def _severity(count: int) -> str:
    if count >= 20:
        return "critical"
    if count >= 10:
        return "high"
    if count >= 5:
        return "medium"
    return "low"


def _recommendation(app_name: str, count: int, severity: str) -> str:
    base = f"{count} usuario(s) han reportado '{app_name}' en los últimos {INCIDENT_WINDOW_MINUTES} minutos."
    if severity == "critical":
        return (
            f"{base} "
            "Incidente masivo crítico. Escalar inmediatamente a nivel 3, "
            "notificar al área propietaria y publicar comunicado general."
        )
    if severity == "high":
        return (
            f"{base} "
            "Escalar a nivel 2. Validar estado del servicio y coordinar con el área técnica. "
            "Evitar crear tickets duplicados — esperar resolución centralizada."
        )
    return (
        f"{base} "
        "Validar estado del servicio. Si se confirma caída, escalar a soporte N2 "
        "y comunicar a los usuarios afectados."
    )


class IncidentService:

    async def check_and_create_alert(
        self,
        db: AsyncSession,
        app_name: Optional[str],
        app_or_url: Optional[str],
        conversation_id: Optional[str],
        category: Optional[str] = None,
    ) -> Optional[IncidentAlert]:
        """
        Verifica si hay un incidente masivo en curso y crea/actualiza la alerta.

        Returns:
            IncidentAlert si se superó el umbral, None en caso contrario.
        """
        # Necesitamos al menos el nombre del aplicativo o la URL para agrupar
        identifier = app_name or app_or_url
        if not identifier:
            return None

        window_start = datetime.now(timezone.utc) - timedelta(minutes=INCIDENT_WINDOW_MINUTES)

        # Contar conversaciones distintas que reportaron este aplicativo en la ventana
        # Buscamos en metadata_.detected_url o en el application_status_snapshot
        recent_count = (await db.execute(
            select(func.count(Conversation.id.distinct())).where(
                Conversation.created_at >= window_start,
                Conversation.metadata_.op("->>")(  # type: ignore[attr-defined]
                    "case"
                ).op("->>")(
                    "slots"
                ).op("->>")(
                    "app_or_url"
                ).ilike(f"%{(app_or_url or app_name or '').split('/')[0]}%")
                if app_or_url
                else Conversation.metadata_.op("->>")(
                    "case"
                ).op("->>")(
                    "slots"
                ).op("->>")(
                    "app_or_url"
                ).ilike(f"%{app_name}%"),
            )
        )).scalar() or 0

        if recent_count < INCIDENT_THRESHOLD:
            return None

        severity = _severity(recent_count)

        # ¿Ya existe alerta abierta para este aplicativo en la ventana?
        existing = (await db.execute(
            select(IncidentAlert).where(
                IncidentAlert.status == "open",
                IncidentAlert.application_name.ilike(f"%{identifier}%"),
                IncidentAlert.first_seen_at >= window_start,
            ).order_by(IncidentAlert.created_at.desc()).limit(1)
        )).scalar_one_or_none()

        if existing:
            # Actualiza el conteo y severity
            existing.affected_users_count = max(existing.affected_users_count, recent_count)
            existing.severity = severity
            existing.last_seen_at = datetime.now(timezone.utc)
            existing.recommendation = _recommendation(identifier, recent_count, severity)
            # Agrega el conversation_id a la lista si no está
            if conversation_id:
                ids = list(existing.conversation_ids or [])
                if conversation_id not in ids:
                    ids.append(conversation_id)
                    existing.conversation_ids = ids
            await db.flush()
            logger.info(
                "incident_alert_updated",
                app=identifier, count=recent_count, severity=severity,
                alert_id=str(existing.id),
            )
            return existing

        # Crea nueva alerta
        alert = IncidentAlert(
            application_name=app_name or identifier[:255],
            app_or_url=app_or_url,
            category=category or "unknown",
            severity=severity,
            affected_users_count=recent_count,
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            status="open",
            recommendation=_recommendation(identifier, recent_count, severity),
            conversation_ids=[conversation_id] if conversation_id else [],
        )
        db.add(alert)
        await db.flush()

        logger.info(
            "incident_alert_created",
            app=identifier, count=recent_count, severity=severity,
            alert_id=str(alert.id),
        )
        return alert

    async def list_open(self, db: AsyncSession, limit: int = 20):
        rows = (await db.execute(
            select(IncidentAlert)
            .where(IncidentAlert.status == "open")
            .order_by(IncidentAlert.affected_users_count.desc(), IncidentAlert.created_at.desc())
            .limit(limit)
        )).scalars().all()
        return rows

    async def acknowledge(
        self, db: AsyncSession, alert_id, admin_id, notes: Optional[str] = None
    ) -> Optional[IncidentAlert]:
        alert = await db.get(IncidentAlert, alert_id)
        if not alert:
            return None
        alert.status = "acknowledged"
        alert.acknowledged_by = admin_id
        alert.acknowledged_at = datetime.now(timezone.utc)
        if notes:
            alert.notes = notes
        await db.flush()
        return alert

    async def resolve(
        self, db: AsyncSession, alert_id, admin_id, notes: Optional[str] = None
    ) -> Optional[IncidentAlert]:
        alert = await db.get(IncidentAlert, alert_id)
        if not alert:
            return None
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        if notes:
            alert.notes = notes
        await db.flush()
        return alert


incident_service = IncidentService()
