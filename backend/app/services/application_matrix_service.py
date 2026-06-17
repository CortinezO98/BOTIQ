from __future__ import annotations

import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application_matrix import ApplicationMatrix

# Palabras demasiado cortas no sirven como evidencia de que el usuario está
# hablando de un aplicativo/portal/servidor específico (p. ej. "SO", "IT").
_MIN_CANDIDATE_LENGTH = 4

# Umbral mínimo para aceptar un match por texto libre como confiable.
# Antes era 50: UNA sola coincidencia débil (score 55, ver _term_matches)
# bastaba para disparar falsos positivos sobre mensajes largos sin relación
# real con ningún aplicativo (p. ej. preguntas de procedimiento genérico).
_MIN_MATCH_SCORE = 80


class ApplicationMatrixService:
    """
    Servicio de consulta de la matriz interna de aplicaciones.

    La matriz permite que BOTIQ relacione:
    URL / IP / nombre de portal -> servidor / ambiente / criticidad / grupo de soporte.
    """

    def normalize_url(self, value: Optional[str]) -> str:
        if not value:
            return ""
        raw = value.strip().lower()
        if not raw:
            return ""
        if not raw.startswith(("http://", "https://")):
            raw = "https://" + raw
        parsed = urlparse(raw)
        host = (parsed.netloc or parsed.path).lower().replace("www.", "")
        path = parsed.path.rstrip("/")
        return f"{host}{path}".strip("/")

    def _term_matches(self, candidate: str, text: str) -> bool:
        """
        Coincidencia por palabra completa (no substring) y con longitud mínima.

        Antes se usaba `candidate in text`, lo que permitía que cualquier
        app_name/portal_name/server_name corto apareciera "por accidente"
        dentro de un mensaje largo y no relacionado, generando falsos
        positivos de "aplicativo encontrado".
        """
        if not candidate or len(candidate) < _MIN_CANDIDATE_LENGTH:
            return False
        return re.search(r"\b" + re.escape(candidate) + r"\b", text) is not None

    async def lookup(
        self,
        db: AsyncSession,
        url: Optional[str] = None,
        ip: Optional[str] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        rows = (
            await db.execute(
                select(ApplicationMatrix)
                .where(ApplicationMatrix.is_active == True)
                .order_by(ApplicationMatrix.created_at.desc())
                .limit(500)
            )
        ).scalars().all()

        if not rows:
            return {"found": False, "source": "application_matrix", "message": "Matriz de aplicaciones sin registros activos."}

        url_norm = self.normalize_url(url)
        ip_norm = (ip or "").strip().lower()
        q_norm = (query or "").strip().lower()

        best = None
        best_score = 0

        for row in rows:
            score = 0

            row_url = self.normalize_url(row.url_pattern)
            row_ip = (row.ip_address or "").strip().lower()
            app_name = (row.app_name or "").lower()
            portal_name = (row.portal_name or "").lower()
            server_name = (row.server_name or "").lower()

            if url_norm and row_url:
                if url_norm == row_url:
                    score += 100
                elif row_url in url_norm or url_norm in row_url:
                    score += 80

            if ip_norm and row_ip and ip_norm == row_ip:
                score += 100

            if q_norm:
                # Solo comparamos contra nombres "humanos" (app/portal/servidor).
                # row_url y row_ip ya se evalúan arriba con comparación exacta/
                # normalizada; incluirlos aquí como substring del mensaje libre
                # era una fuente extra de falsos positivos.
                for candidate in [app_name, portal_name, server_name]:
                    if self._term_matches(candidate, q_norm):
                        score += 55

            if score > best_score:
                best_score = score
                best = row

        if not best or best_score < _MIN_MATCH_SCORE:
            return {"found": False, "source": "application_matrix", "message": "No se encontró relación en la matriz de aplicaciones."}

        return {
            "found": True,
            "source": "application_matrix",
            "score": best_score,
            "application": self.to_dict(best),
            "message": (
                f"Aplicativo relacionado: {best.app_name}. "
                f"Servidor: {best.server_name or 'No registrado'}. "
                f"Ambiente: {best.environment or 'No registrado'}. "
                f"Criticidad: {best.criticality or 'No registrada'}."
            ),
        }

    def to_dict(self, row: ApplicationMatrix) -> Dict[str, Any]:
        return {
            "id": str(row.id),
            "app_name": row.app_name,
            "portal_name": row.portal_name,
            "url_pattern": row.url_pattern,
            "ip_address": row.ip_address,
            "server_name": row.server_name,
            "environment": row.environment,
            "criticality": row.criticality,
            "owner_area": row.owner_area,
            "support_group": row.support_group,
            "status_source": row.status_source,
            "notes": row.notes,
            "is_active": row.is_active,
        }

    def format_for_prompt(self, matrix_result: Optional[Dict[str, Any]]) -> str:
        if not matrix_result or not matrix_result.get("found"):
            return "No hay relación encontrada en la matriz interna de aplicaciones."

        app = matrix_result.get("application") or {}
        return (
            "Matriz interna de aplicaciones:\n"
            f"- Aplicativo: {app.get('app_name') or 'N/A'}\n"
            f"- Portal: {app.get('portal_name') or 'N/A'}\n"
            f"- URL registrada: {app.get('url_pattern') or 'N/A'}\n"
            f"- IP registrada: {app.get('ip_address') or 'N/A'}\n"
            f"- Servidor: {app.get('server_name') or 'N/A'}\n"
            f"- Ambiente: {app.get('environment') or 'N/A'}\n"
            f"- Criticidad: {app.get('criticality') or 'N/A'}\n"
            f"- Grupo soporte: {app.get('support_group') or 'N/A'}\n"
            f"- Observaciones: {app.get('notes') or 'N/A'}"
        )


application_matrix_service = ApplicationMatrixService()