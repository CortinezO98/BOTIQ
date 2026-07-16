from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditService:
    """Servicio centralizado para registrar eventos de auditoría en BOTIQ."""

    async def log(
        self,
        db: AsyncSession,
        action: str,
        user_id=None,
        module: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            module=module,
            metadata_=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit_log)
        await db.flush()
        return audit_log


audit_service = AuditService()
