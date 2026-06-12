from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditService:
    async def log(
        self,
        db: AsyncSession,
        action: str,
        user_id=None,
        module: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        log = AuditLog(
            user_id=user_id,
            action=action,
            module=module,
            metadata_=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(log)
        await db.flush()
        return log


audit_service = AuditService()
