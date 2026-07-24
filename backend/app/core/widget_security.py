from __future__ import annotations

import secrets
from typing import Any, Dict
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.config import settings


def normalize_origin(value: str) -> str:
    """Normaliza un origin a scheme://host[:port] y rechaza rutas/query."""
    raw = str(value or "").strip()
    parsed = urlsplit(raw)

    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Origin inválido; debe usar http:// o https://")
    if parsed.username or parsed.password:
        raise ValueError("Origin inválido; no puede incluir credenciales")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Origin inválido; no puede incluir ruta, query o fragmento")

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("Origin inválido")

    port = parsed.port
    if port and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        return f"{scheme}://{hostname}:{port}"
    return f"{scheme}://{hostname}"


def get_widget_portal(portal_id: str) -> Dict[str, Any]:
    normalized_id = str(portal_id or "").strip()
    for portal in settings.get_widget_portals():
        if portal["id"] == normalized_id:
            return portal
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Integración de portal no autorizada.",
    )


def validate_portal_secret(portal: Dict[str, Any], provided_secret: str) -> None:
    expected = str(portal.get("secret") or "")
    provided = str(provided_secret or "")
    if not expected or not secrets.compare_digest(expected, provided):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales de integración inválidas.",
        )


def validate_portal_origin(portal: Dict[str, Any], origin: str) -> str:
    try:
        normalized = normalize_origin(origin)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    allowed = {
        normalize_origin(item)
        for item in (portal.get("origins") or [])
    }
    if normalized not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El portal no está autorizado para incrustar BOTIQ.",
        )
    return normalized


def validate_widget_request_context(request: Request, claims: Dict[str, Any]) -> None:
    """Valida los headers de contexto enviados por el iframe de BOTIQ.

    El iframe agrega estos headers a todas las llamadas autenticadas:
    - X-BOTIQ-Portal-Id
    - X-BOTIQ-Parent-Origin

    No sustituyen la firma del JWT; son una segunda verificación para impedir
    que un token de un portal se use accidentalmente desde otro contexto.
    """
    portal_id = str(request.headers.get("X-BOTIQ-Portal-Id") or "").strip()
    parent_origin_raw = str(
        request.headers.get("X-BOTIQ-Parent-Origin") or ""
    ).strip()

    if portal_id != claims.get("portal_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contexto de portal inválido.",
        )

    try:
        parent_origin = normalize_origin(parent_origin_raw)
        token_origin = normalize_origin(claims.get("allowed_origin") or "")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contexto de origen inválido.",
        ) from exc

    if parent_origin != token_origin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token no pertenece al portal solicitante.",
        )
