"""
Integración segura de BOTIQ con Aranda Service Desk ASDK API v8.6.

Principios aplicados:
- El ticket se crea únicamente como ÚLTIMA INSTANCIA.
- Se exige confirmación explícita del usuario.
- Se exige que BOTIQ haya agotado los intentos mínimos de resolución.
- Se impide crear más de un caso para la misma conversación.
- La autenticación usa username/password y el sessionId de Aranda; no Bearer API key.
- La sesión se cierra al terminar para liberar la licencia de especialista.
- No se reintenta automáticamente una creación tras un timeout ambiguo.
- La contraseña y el sessionId nunca se escriben en logs ni respuestas.
- Se conserva trazabilidad mediante un correlation_id BOTIQ incluido en el caso.

Documento de referencia: Aranda Service Desk ASDK API, rutas api/v8.6.
"""
from __future__ import annotations

import asyncio
import json
import mimetypes
import ssl
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional, Sequence, Tuple, Union

import httpx

from app.core.config import settings
from app.core.logging_config import get_logger
from app.models.conversation import Conversation
from app.models.user import User

logger = get_logger(__name__, module="aranda")

JsonValue = Union[None, bool, int, float, str, List[Any], Dict[str, Any]]
FieldValueArray = List[Dict[str, Any]]


class ArandaIntegrationError(RuntimeError):
    """Error controlado de comunicación o contrato con Aranda."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "ArandaIntegrationError",
        http_status: Optional[int] = None,
        ambiguous: bool = False,
        response_excerpt: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.ambiguous = ambiguous
        self.response_excerpt = response_excerpt


@dataclass(frozen=True)
class ArandaSession:
    """Sesión temporal retornada por /user/login."""

    user_id: int
    session_id: str


@dataclass(frozen=True)
class LastResortDecision:
    allowed: bool
    reason: str
    code: str


class ArandaService:
    """
    Cliente de alto nivel para Aranda ASDK.

    Este servicio mantiene compatibilidad con la firma anterior de
    ``create_ticket``. El nuevo parámetro ``explicit_confirmation`` es opcional:
    cuando no se envía, intenta inferir la confirmación desde
    ``conversation.metadata_["case"]["intent"] == "ticket_confirmation"``.

    La creación queda protegida también dentro de este servicio. Por tanto,
    aunque otra capa intente llamar a Aranda antes de tiempo, la solicitud se
    bloquea si la conversación aún no es elegible como última instancia.
    """

    ITEM_TYPES = {1, 2, 3, 4}
    DETAIL_LEVELS = {0, 1, 2}

    # Aranda usa una licencia como si un especialista ingresara a consola.
    # El lock evita sesiones simultáneas dentro del mismo proceso de Python.
    # En despliegues con múltiples workers, cada worker puede mantener como
    # máximo una operación Aranda a la vez. Para alta concurrencia se recomienda
    # mover las creaciones a un worker dedicado/cola.
    _session_lock = asyncio.Lock()

    _PROTECTED_UPDATE_FIELDS = {
        "authorid",
        "itemid",
        "itemtype",
        "composeditemid",
        "projectid",
    }

    # ------------------------------------------------------------------
    # Configuración y utilidades de contrato
    # ------------------------------------------------------------------

    def is_connection_configured(self) -> bool:
        """Indica si BOTIQ puede autenticar y ejecutar operaciones de lectura."""
        report = self.connection_report()
        return bool(report["enabled"] and report["valid"])

    def is_configured(self) -> bool:
        """Compatibilidad: indica si la CREACIÓN de casos está configurada."""
        report = self.configuration_report()
        return bool(report["enabled"] and report["creation_enabled"] and report["valid"])

    def connection_report(self) -> Dict[str, Any]:
        """Diagnóstico de conexión/lectura sin exigir IDs de creación."""
        enabled = bool(getattr(settings, "ARANDA_ENABLED", False))
        required_text = {
            "ARANDA_API_URL": getattr(settings, "ARANDA_API_URL", ""),
            "ARANDA_USERNAME": getattr(settings, "ARANDA_USERNAME", ""),
            "ARANDA_PASSWORD": getattr(settings, "ARANDA_PASSWORD", ""),
        }
        missing: List[str] = []
        if enabled:
            missing.extend(
                name for name, value in required_text.items()
                if not str(value or "").strip()
            )

        base_url = str(getattr(settings, "ARANDA_API_URL", "") or "").strip()
        if enabled and base_url:
            parsed_url = urlparse(base_url)
            if parsed_url.scheme.lower() != "https":
                missing.append("ARANDA_API_URL debe usar HTTPS")
            if parsed_url.username or parsed_url.password:
                missing.append("ARANDA_API_URL no debe contener credenciales")
            allowed_hosts = {
                host.strip().lower()
                for host in str(getattr(settings, "ARANDA_ALLOWED_HOSTS", "") or "").split(",")
                if host.strip()
            }
            if allowed_hosts and str(parsed_url.hostname or "").lower() not in allowed_hosts:
                missing.append("El host de ARANDA_API_URL no está permitido en ARANDA_ALLOWED_HOSTS")

        ca_bundle = str(getattr(settings, "ARANDA_CA_BUNDLE", "") or "").strip()
        if enabled and ca_bundle and not Path(ca_bundle).is_file():
            missing.append("ARANDA_CA_BUNDLE no existe o no es un archivo")

        return {
            "enabled": enabled,
            "valid": enabled and not missing,
            "missing_or_invalid": sorted(set(missing)),
            "api_base": self._api_base(safe=True) if base_url else None,
            "verify_tls": bool(getattr(settings, "ARANDA_VERIFY_TLS", True)),
            "close_session_after_request": bool(
                getattr(settings, "ARANDA_CLOSE_SESSION_AFTER_REQUEST", True)
            ),
        }

    def configuration_report(self) -> Dict[str, Any]:
        """Diagnóstico completo para CREAR casos, sin exponer secretos."""
        connection = self.connection_report()
        enabled = bool(connection["enabled"])
        creation_enabled = bool(getattr(settings, "ARANDA_CREATION_ENABLED", False))
        missing: List[str] = list(connection["missing_or_invalid"])

        if enabled and not creation_enabled:
            missing.append("ARANDA_CREATION_ENABLED=false")

        required_ids = {
            "ARANDA_PROJECT_ID": getattr(settings, "ARANDA_PROJECT_ID", 0),
            "ARANDA_CATEGORY_ID": getattr(settings, "ARANDA_CATEGORY_ID", 0),
            "ARANDA_GROUP_ID": getattr(settings, "ARANDA_GROUP_ID", 0),
            "ARANDA_SERVICE_ID": getattr(settings, "ARANDA_SERVICE_ID", 0),
            "ARANDA_SLA_ID": getattr(settings, "ARANDA_SLA_ID", 0),
            "ARANDA_REGISTRY_TYPE_ID": getattr(settings, "ARANDA_REGISTRY_TYPE_ID", 0),
        }
        if enabled and creation_enabled:
            for name, value in required_ids.items():
                if self._as_positive_int(value) is None:
                    missing.append(name)

            item_type = self._as_int(
                getattr(settings, "ARANDA_DEFAULT_ITEM_TYPE", 1), default=1
            )
            if item_type not in self.ITEM_TYPES:
                missing.append("ARANDA_DEFAULT_ITEM_TYPE debe estar entre 1 y 4")

        return {
            **connection,
            "creation_enabled": creation_enabled,
            "valid": bool(connection["valid"] and creation_enabled and not missing),
            "missing_or_invalid": sorted(set(missing)),
        }

    def _api_base(self, *, safe: bool = False) -> str:
        """
        Normaliza cualquiera de estas configuraciones:
        - https://host/ASDKAPI
        - https://host/ASDKAPI/api/v8.6
        - https://host/ASDKAPI/api/v8.6/user/login
        """
        raw = str(getattr(settings, "ARANDA_API_URL", "") or "").strip().rstrip("/")
        if not raw:
            return ""

        lowered = raw.lower()
        login_suffix = "/user/login"
        if lowered.endswith(login_suffix):
            raw = raw[: -len(login_suffix)]
            lowered = raw.lower()

        if lowered.endswith("/api/v8.6"):
            base = raw
        elif lowered.endswith("/asdkapi"):
            base = f"{raw}/api/v8.6"
        elif "/api/v8.6/" in lowered:
            index = lowered.index("/api/v8.6/")
            base = raw[: index + len("/api/v8.6")]
        else:
            base = f"{raw}/api/v8.6"

        # safe existe para dejar claro que esta función nunca agrega credenciales.
        return base.rstrip("/")

    def _http_timeout(self) -> httpx.Timeout:
        total = max(1.0, float(getattr(settings, "ARANDA_TIMEOUT_SECONDS", 15)))
        connect = max(1.0, float(getattr(settings, "ARANDA_CONNECT_TIMEOUT_SECONDS", 5)))
        return httpx.Timeout(timeout=total, connect=connect)

    def _verify_tls(self) -> Union[bool, ssl.SSLContext]:
        verify = bool(getattr(settings, "ARANDA_VERIFY_TLS", True))
        ca_bundle = str(getattr(settings, "ARANDA_CA_BUNDLE", "") or "").strip()
        if ca_bundle:
            return ssl.create_default_context(cafile=ca_bundle)
        return verify

    def _new_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._http_timeout(),
            verify=self._verify_tls(),
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": f"BOTIQ/{getattr(settings, 'APP_VERSION', 'unknown')}",
            },
        )

    @staticmethod
    def _field(name: str, value: Any) -> Dict[str, Any]:
        return {"Field": name, "Value": value}

    @staticmethod
    def _field_values_to_dict(payload: Any) -> Dict[str, Any]:
        """Convierte la respuesta [{Field, Value}, ...] en dict case-insensitive."""
        if not isinstance(payload, list):
            raise ArandaIntegrationError(
                "Aranda devolvió una estructura inesperada.",
                code="InvalidArandaResponse",
            )

        result: Dict[str, Any] = {}
        for entry in payload:
            if not isinstance(entry, Mapping):
                continue
            field = str(entry.get("Field") or "").strip()
            if field:
                result[field.lower()] = entry.get("Value")
        return result

    @staticmethod
    def _as_int(value: Any, *, default: int = 0) -> int:
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    @classmethod
    def _as_positive_int(cls, value: Any) -> Optional[int]:
        parsed = cls._as_int(value, default=0)
        return parsed if parsed > 0 else None

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"true", "1", "yes", "si", "sí"}

    @staticmethod
    def _safe_excerpt(value: Any, max_chars: int = 500) -> str:
        """Fragmento seguro para diagnóstico; nunca se usa con credenciales."""
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False, default=str)
        else:
            text = str(value or "")
        text = " ".join(text.split())
        return text[:max_chars]

    @classmethod
    def _extract_error_code(cls, response: httpx.Response, payload: Any = None) -> str:
        candidates: List[str] = []
        if isinstance(payload, dict):
            for key in ("message", "Message", "error", "Error", "detail", "Detail"):
                if payload.get(key):
                    candidates.append(str(payload[key]))
        elif isinstance(payload, list):
            try:
                mapped = cls._field_values_to_dict(payload)
                candidates.extend(str(v) for v in mapped.values() if v)
            except ArandaIntegrationError:
                pass

        if response.text:
            candidates.append(response.text)

        known_prefixes = (
            "Invalid",
            "Unauthorized",
            "Failure",
            "CaseIsClosed",
            "NonExistent",
            "DeviceNameIsRequire",
        )
        for candidate in candidates:
            compact = candidate.replace('"', " ").replace("'", " ")
            for token in compact.replace("\r", " ").replace("\n", " ").split():
                cleaned = token.strip("[]{}(),:;.")
                if cleaned.startswith(known_prefixes):
                    return cleaned[:120]

        return f"HTTP_{response.status_code}"

    async def _decode_response(self, response: httpx.Response) -> JsonValue:
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        *,
        session_id: Optional[str] = None,
        json_body: Any = None,
        data: Any = None,
        files: Any = None,
        params: Optional[Mapping[str, Any]] = None,
    ) -> Tuple[httpx.Response, JsonValue]:
        headers: Dict[str, str] = {}
        if session_id:
            # ASDK espera el sessionId directamente, sin prefijo Bearer.
            headers["Authorization"] = session_id
        if files is None:
            headers["Content-Type"] = "application/json"

        url = f"{self._api_base()}/{path.lstrip('/')}"
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                json=json_body,
                data=data,
                files=files,
                params=params,
            )
        except httpx.TimeoutException as exc:
            raise ArandaIntegrationError(
                "Tiempo de espera agotado comunicándose con Aranda.",
                code="ArandaTimeout",
                ambiguous=method.upper() == "POST" and "item/add/" in path,
            ) from exc
        except httpx.TransportError as exc:
            raise ArandaIntegrationError(
                "No fue posible establecer comunicación segura con Aranda.",
                code="ArandaTransportError",
                ambiguous=method.upper() == "POST" and "item/add/" in path,
            ) from exc

        payload = await self._decode_response(response)
        if response.status_code >= 400:
            error_code = self._extract_error_code(response, payload)
            raise ArandaIntegrationError(
                "Aranda rechazó la operación solicitada.",
                code=error_code,
                http_status=response.status_code,
                response_excerpt=self._safe_excerpt(payload),
            )

        return response, payload

    # ------------------------------------------------------------------
    # Manejo de sesión
    # ------------------------------------------------------------------

    async def _login(self, client: httpx.AsyncClient) -> ArandaSession:
        body: FieldValueArray = [
            self._field("username", str(getattr(settings, "ARANDA_USERNAME", "")).strip()),
            self._field("password", str(getattr(settings, "ARANDA_PASSWORD", ""))),
        ]

        language_id = self._as_positive_int(getattr(settings, "ARANDA_LANGUAGE_ID", 2))
        console_id = self._as_positive_int(getattr(settings, "ARANDA_CONSOLE_ID", 0))
        console_version = str(getattr(settings, "ARANDA_CONSOLE_VERSION", "") or "").strip()

        if language_id is not None:
            body.append(self._field("languageId", language_id))
        if console_id is not None:
            body.append(self._field("consoleId", console_id))
        if console_version:
            body.append(self._field("consoleVersion", console_version[:100]))

        _, payload = await self._request(client, "POST", "user/login", json_body=body)
        mapped = self._field_values_to_dict(payload)

        if not self._as_bool(mapped.get("result")):
            raise ArandaIntegrationError(
                "Aranda no confirmó el inicio de sesión.",
                code="ArandaLoginFailed",
            )

        user_id = self._as_positive_int(mapped.get("userid"))
        session_id = str(mapped.get("sessionid") or "").strip()
        if user_id is None or not session_id:
            raise ArandaIntegrationError(
                "La respuesta de inicio de sesión no contiene userId/sessionId válidos.",
                code="InvalidLoginResponse",
            )

        logger.info("aranda_login_success", aranda_user_id=user_id)
        return ArandaSession(user_id=user_id, session_id=session_id)

    async def _renew_session(self, client: httpx.AsyncClient, session: ArandaSession) -> None:
        response, _ = await self._request(
            client,
            "POST",
            "session/renew",
            session_id=session.session_id,
            json_body=None,
        )
        if response.status_code != 200:
            raise ArandaIntegrationError(
                "Aranda no renovó la sesión.",
                code="ArandaSessionRenewFailed",
                http_status=response.status_code,
            )

    async def _logout(self, client: httpx.AsyncClient, session: ArandaSession) -> None:
        try:
            await self._request(
                client,
                "POST",
                "user/logout",
                session_id=session.session_id,
                json_body=None,
            )
            logger.info("aranda_logout_success", aranda_user_id=session.user_id)
        except ArandaIntegrationError as exc:
            # El cierre no debe ocultar el resultado de la operación principal.
            logger.warning(
                "aranda_logout_failed",
                aranda_user_id=session.user_id,
                error_code=exc.code,
                http_status=exc.http_status,
            )

    @asynccontextmanager
    async def _authenticated_session(self) -> AsyncIterator[Tuple[httpx.AsyncClient, ArandaSession]]:
        """Abre una sesión corta y siempre la cierra para liberar la licencia."""
        report = self.connection_report()
        if not report["valid"]:
            raise ArandaIntegrationError(
                "La conexión de Aranda no está completamente configurada.",
                code="InvalidArandaConfiguration",
                response_excerpt=", ".join(report["missing_or_invalid"]),
            )

        async with self._session_lock:
            async with self._new_client() as client:
                session = await self._login(client)
                try:
                    yield client, session
                finally:
                    # ASDK consume licencia de especialista. El logout es
                    # obligatorio para no dejar licencias ocupadas.
                    await self._logout(client, session)

    async def test_connection(self) -> Dict[str, Any]:
        """Prueba login + renovación + logout, sin crear ningún caso."""
        report = self.connection_report()
        if not report["valid"]:
            return {
                "ok": False,
                "status": "invalid_connection_configuration",
                "missing_or_invalid": report["missing_or_invalid"],
                "message": "La conexión de Aranda no está completamente configurada.",
            }

        started = time.perf_counter()
        try:
            async with self._authenticated_session() as (client, session):
                await self._renew_session(client, session)
                return {
                    "ok": True,
                    "status": "connected",
                    "aranda_user_id": session.user_id,
                    "response_time_ms": round((time.perf_counter() - started) * 1000, 2),
                    "message": "Autenticación y renovación de sesión correctas.",
                }
        except ArandaIntegrationError as exc:
            logger.error(
                "aranda_connection_test_failed",
                error_code=exc.code,
                http_status=exc.http_status,
            )
            return {
                "ok": False,
                "status": "connection_error",
                "error_code": exc.code,
                "http_status": exc.http_status,
                "message": "No fue posible validar la conexión con Aranda.",
            }

    # ------------------------------------------------------------------
    # Política obligatoria: ticket solo como última instancia
    # ------------------------------------------------------------------

    def _infer_explicit_confirmation(
        self,
        conversation: Conversation,
        explicit_confirmation: Optional[bool],
    ) -> bool:
        if explicit_confirmation is not None:
            return bool(explicit_confirmation)

        metadata = conversation.metadata_ or {}
        case = metadata.get("case") if isinstance(metadata, dict) else {}
        if not isinstance(case, dict):
            return False

        return bool(
            case.get("ticket_confirmation_received") is True
            or str(case.get("intent") or "").lower() == "ticket_confirmation"
        )

    def validate_last_resort_policy(
        self,
        conversation: Conversation,
        *,
        explicit_confirmation: Optional[bool],
        subject: str,
        description: str,
    ) -> LastResortDecision:
        """
        Defensa en profundidad para impedir tickets prematuros.

        No existe excepción automática para HTTP 5xx: aun en un incidente
        crítico, BOTIQ debe recopilar los datos, ejecutar las validaciones
        configuradas y obtener confirmación explícita. La urgencia/prioridad se
        refleja en el caso, pero no elimina el control de última instancia.
        """
        if conversation.escalated_to_aranda or conversation.aranda_ticket_id:
            return LastResortDecision(
                False,
                f"Esta conversación ya tiene un ticket asociado: {conversation.aranda_ticket_id or 'registrado'}.",
                "duplicate_ticket",
            )

        metadata = conversation.metadata_ or {}
        aranda_tracking = metadata.get("aranda") if isinstance(metadata, dict) else {}
        aranda_tracking = aranda_tracking if isinstance(aranda_tracking, dict) else {}
        if (
            str(conversation.aranda_ticket_status or "").lower() == "creation_unknown"
            or bool(aranda_tracking.get("requires_reconciliation"))
        ):
            return LastResortDecision(
                False,
                "Existe una creación anterior sin confirmación. Debe conciliarse en Aranda antes de reintentar.",
                "reconciliation_required",
            )

        if not self._infer_explicit_confirmation(conversation, explicit_confirmation):
            return LastResortDecision(
                False,
                "Para crear el ticket necesito la confirmación explícita del usuario.",
                "explicit_confirmation_required",
            )

        attempts = int(conversation.resolution_attempts or 0)
        minimum = max(1, int(getattr(settings, "MIN_RESOLUTION_ATTEMPTS_BEFORE_TICKET", 2)))
        if attempts < minimum:
            return LastResortDecision(
                False,
                f"BOTIQ todavía no ha agotado las {minimum} validaciones mínimas de solución.",
                "resolution_attempts_pending",
            )

        if not bool(conversation.ticket_eligible):
            return LastResortDecision(
                False,
                "La conversación todavía no fue marcada como no resuelta y elegible para escalamiento.",
                "conversation_not_eligible",
            )

        case = metadata.get("case") if isinstance(metadata, dict) else {}
        slots = case.get("slots") if isinstance(case, dict) else {}
        slots = slots if isinstance(slots, dict) else {}

        target = (
            conversation.detected_url
            or conversation.detected_ip
            or slots.get("app_or_url")
            or slots.get("url")
            or slots.get("ip")
            or slots.get("device_or_service")
            or slots.get("topic")
        )
        symptom = slots.get("error_or_symptom") or slots.get("error_code") or slots.get("evidence")

        missing: List[str] = []
        if not str(target or "").strip():
            missing.append("aplicativo, URL, IP, equipo o servicio afectado")
        if not str(symptom or "").strip() and len(str(description or "").strip()) < 25:
            missing.append("error, síntoma o descripción suficientemente detallada")
        if len(str(subject or "").strip()) < 5:
            missing.append("asunto del caso")

        if missing:
            return LastResortDecision(
                False,
                "Faltan datos mínimos: " + ", ".join(missing) + ".",
                "minimum_case_data_missing",
            )

        return LastResortDecision(True, "Última instancia validada.", "allowed")

    # ------------------------------------------------------------------
    # Creación de caso
    # ------------------------------------------------------------------

    def _configured_case_fields(
        self,
        *,
        session_user_id: int,
        subject: str,
        description: str,
        field_overrides: Optional[Mapping[str, Any]] = None,
    ) -> FieldValueArray:
        overrides: Dict[str, Any] = {
            str(key).strip().lower(): value
            for key, value in (field_overrides or {}).items()
            if str(key).strip()
        }

        def choose(field_name: str, setting_name: str, default: Any = None) -> Any:
            override = overrides.get(field_name.lower())
            if override not in (None, ""):
                return override
            return getattr(settings, setting_name, default)

        max_subject = max(20, int(getattr(settings, "ARANDA_MAX_SUBJECT_CHARS", 180)))
        max_description = max(1000, int(getattr(settings, "ARANDA_MAX_DESCRIPTION_CHARS", 12000)))

        values: List[Tuple[str, Any, bool]] = [
            ("AuthorId", choose("AuthorId", "ARANDA_AUTHOR_ID", session_user_id) or session_user_id, True),
            ("CategoryId", choose("CategoryId", "ARANDA_CATEGORY_ID", 0), True),
            ("Description", str(description).strip()[:max_description], True),
            ("GroupId", choose("GroupId", "ARANDA_GROUP_ID", 0), True),
            ("ProjectId", choose("ProjectId", "ARANDA_PROJECT_ID", 0), True),
            ("RegistryTypeId", choose("RegistryTypeId", "ARANDA_REGISTRY_TYPE_ID", 0), True),
            ("ServiceId", choose("ServiceId", "ARANDA_SERVICE_ID", 0), True),
            ("Subject", str(subject).strip()[:max_subject], False),
            ("SlaId", choose("SlaId", "ARANDA_SLA_ID", 0), True),
            ("UrgencyId", choose("UrgencyId", "ARANDA_URGENCY_ID", 0), False),
            ("CustomerId", choose("CustomerId", "ARANDA_CUSTOMER_ID", 0), False),
            ("CompanyId", choose("CompanyId", "ARANDA_COMPANY_ID", 0), False),
            ("ResponsibleId", choose("ResponsibleId", "ARANDA_RESPONSIBLE_ID", 0), False),
            ("CiId", choose("CiId", "ARANDA_CI_ID", 0), False),
        ]

        missing: List[str] = []
        body: FieldValueArray = []
        numeric_fields = {
            "AuthorId",
            "CategoryId",
            "GroupId",
            "ProjectId",
            "RegistryTypeId",
            "ServiceId",
            "SlaId",
            "UrgencyId",
            "CustomerId",
            "CompanyId",
            "ResponsibleId",
            "CiId",
        }

        for field_name, value, required in values:
            if field_name in numeric_fields:
                value = self._as_positive_int(value)

            if value in (None, ""):
                if required:
                    missing.append(field_name)
                continue
            body.append(self._field(field_name, value))

        # Permite campos adicionales o ajustes por aplicativo sin cambiar este cliente.
        standard = {name.lower() for name, _, _ in values}
        for key, value in (field_overrides or {}).items():
            if str(key).strip().lower() in standard or value in (None, ""):
                continue
            body.append(self._field(str(key).strip(), value))

        if missing:
            raise ArandaIntegrationError(
                "Faltan identificadores obligatorios para crear el caso: " + ", ".join(missing),
                code="InvalidArandaCaseConfiguration",
            )
        return body

    def _metadata_field_overrides(self, conversation: Conversation) -> Dict[str, Any]:
        metadata = conversation.metadata_ or {}
        if not isinstance(metadata, dict):
            return {}

        # Dos nombres admitidos para facilitar una futura matriz por aplicativo.
        candidates = [metadata.get("aranda_fields")]
        case = metadata.get("case")
        if isinstance(case, dict):
            candidates.append(case.get("aranda_fields"))

        merged: Dict[str, Any] = {}
        for candidate in candidates:
            if isinstance(candidate, dict):
                merged.update(candidate)
        return merged

    async def create_ticket(
        self,
        conversation: Conversation,
        current_user: User,
        subject: str,
        description: str,
        application_status: Optional[Dict[str, Any]] = None,
        *,
        explicit_confirmation: Optional[bool] = None,
        item_type: Optional[int] = None,
        field_overrides: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Crea un caso únicamente si se cumple la política de última instancia.

        ``explicit_confirmation`` debe ser True en el flujo nuevo. Si se omite,
        se infiere desde la metadata del flujo actual para conservar compatibilidad.
        """
        decision = self.validate_last_resort_policy(
            conversation,
            explicit_confirmation=explicit_confirmation,
            subject=subject,
            description=description,
        )
        if not decision.allowed:
            logger.warning(
                "aranda_creation_blocked_by_policy",
                conversation_id=str(conversation.id),
                policy_code=decision.code,
                resolution_attempts=int(conversation.resolution_attempts or 0),
            )
            return {
                "created": False,
                "ticket_id": conversation.aranda_ticket_id,
                "status": "blocked_by_last_resort_policy",
                "policy_code": decision.code,
                "message": decision.reason,
            }

        config = self.configuration_report()
        if not config["valid"]:
            pending_id = f"BOTIQ-PENDING-{str(conversation.id)[:8]}"
            return {
                "created": False,
                "pending_configuration": True,
                "ticket_id": pending_id,
                "status": "pending_aranda_configuration",
                "missing_or_invalid": config["missing_or_invalid"],
                "message": "El caso es elegible, pero Aranda aún no está completamente configurado.",
            }

        case_type = item_type or self._as_int(getattr(settings, "ARANDA_DEFAULT_ITEM_TYPE", 1), default=1)
        if case_type not in self.ITEM_TYPES:
            return {
                "created": False,
                "ticket_id": None,
                "status": "invalid_item_type",
                "error_code": "InvalidItemType",
                "message": "El tipo de caso configurado no es válido.",
            }

        correlation_id = f"BOTIQ-{str(conversation.id)[:8]}-{uuid.uuid4().hex[:10]}".upper()
        final_description = self._compose_description_for_aranda(
            conversation=conversation,
            current_user=current_user,
            description=description,
            application_status=application_status,
            correlation_id=correlation_id,
        )

        overrides = self._metadata_field_overrides(conversation)
        overrides.update(dict(field_overrides or {}))

        started = time.perf_counter()
        try:
            async with self._authenticated_session() as (client, session):
                body = self._configured_case_fields(
                    session_user_id=session.user_id,
                    subject=subject,
                    description=final_description,
                    field_overrides=overrides,
                )

                _, payload = await self._request(
                    client,
                    "POST",
                    f"item/add/{case_type}",
                    session_id=session.session_id,
                    json_body=body,
                )
                mapped = self._field_values_to_dict(payload)

                if not self._as_bool(mapped.get("result")):
                    raise ArandaIntegrationError(
                        "Aranda no confirmó la creación del caso.",
                        code="ArandaCreateResultFalse",
                        response_excerpt=self._safe_excerpt(payload),
                    )

                item_id = self._as_positive_int(mapped.get("itemid"))
                composed_id = str(mapped.get("composeditemid") or "").strip() or None
                if item_id is None:
                    raise ArandaIntegrationError(
                        "La respuesta de creación no contiene itemId válido.",
                        code="InvalidCreateResponse",
                        response_excerpt=self._safe_excerpt(payload),
                    )

                verification: Dict[str, Any]
                status = "created"
                try:
                    case_data = await self._get_case_with_session(
                        client,
                        session,
                        item_id=item_id,
                        item_type=case_type,
                        level=2,
                    )
                    verification = {
                        "verified": True,
                        "state_id": case_data.get("StateId"),
                        "state_name": case_data.get("StateName"),
                        "is_closed": case_data.get("IsClosed"),
                        "project_id": case_data.get("ProjectId"),
                    }
                    status = str(case_data.get("StateName") or "created")
                except ArandaIntegrationError as verify_exc:
                    # La creación ya fue confirmada por item/add; una falla de
                    # consulta posterior no debe convertirla en "no creada".
                    verification = {
                        "verified": False,
                        "error_code": verify_exc.code,
                    }
                    status = "created_unverified"
                    logger.warning(
                        "aranda_case_verification_failed",
                        conversation_id=str(conversation.id),
                        item_id=item_id,
                        error_code=verify_exc.code,
                    )

                display_id = composed_id or str(item_id)
                logger.info(
                    "aranda_case_created",
                    conversation_id=str(conversation.id),
                    item_id=item_id,
                    composed_item_id=composed_id,
                    correlation_id=correlation_id,
                    response_time_ms=round((time.perf_counter() - started) * 1000, 2),
                )
                return {
                    "created": True,
                    "ticket_id": display_id,
                    "item_id": item_id,
                    "composed_item_id": composed_id,
                    "item_type": case_type,
                    "status": status,
                    "correlation_id": correlation_id,
                    "verification": verification,
                    "is_closed": self._as_bool(mapped.get("isclosed")),
                    "response_time_ms": round((time.perf_counter() - started) * 1000, 2),
                    "message": f"Ticket creado correctamente en Aranda: {display_id}",
                }

        except ArandaIntegrationError as exc:
            logger.error(
                "aranda_case_creation_failed",
                conversation_id=str(conversation.id),
                correlation_id=correlation_id,
                error_code=exc.code,
                http_status=exc.http_status,
                ambiguous=exc.ambiguous,
            )
            if exc.ambiguous:
                return {
                    "created": False,
                    "ticket_id": None,
                    "status": "creation_unknown",
                    "correlation_id": correlation_id,
                    "error_code": exc.code,
                    "requires_reconciliation": True,
                    "message": (
                        "Aranda no confirmó la operación. Para evitar duplicados, "
                        "el caso quedó pendiente de conciliación y no se reintentará automáticamente."
                    ),
                }

            return {
                "created": False,
                "ticket_id": None,
                "status": "error",
                "correlation_id": correlation_id,
                "error_code": exc.code,
                "http_status": exc.http_status,
                "message": "No fue posible registrar el caso en Aranda en este momento.",
            }
        except Exception as exc:  # defensa final: no exponer información interna
            logger.exception(
                "aranda_unexpected_creation_error",
                conversation_id=str(conversation.id),
                correlation_id=correlation_id,
                exception_type=type(exc).__name__,
            )
            return {
                "created": False,
                "ticket_id": None,
                "status": "error",
                "correlation_id": correlation_id,
                "error_code": "UnexpectedArandaError",
                "message": "No fue posible registrar el caso en Aranda en este momento.",
            }

    def _compose_description_for_aranda(
        self,
        *,
        conversation: Conversation,
        current_user: User,
        description: str,
        application_status: Optional[Dict[str, Any]],
        correlation_id: str,
    ) -> str:
        status = application_status or conversation.application_status_snapshot or {}
        # La referencia se ubica al principio para que nunca se pierda por
        # truncamiento y permita conciliar un timeout sin crear duplicados.
        lines = [
            "--- Trazabilidad BOTIQ ---",
            f"Referencia: {correlation_id}",
            f"Conversación: {conversation.id}",
            f"Sesión BOTIQ: {conversation.session_id or 'No disponible'}",
            f"Perfil seleccionado: {conversation.selected_profile or 'No disponible'}",
            f"Usuario: {getattr(current_user, 'full_name', None) or 'No disponible'}",
            f"Correo: {getattr(current_user, 'email', None) or 'No disponible'}",
            f"Intentos de solución agotados: {conversation.resolution_attempts or 0}",
            f"URL detectada: {conversation.detected_url or 'No registrada'}",
            f"IP detectada: {conversation.detected_ip or 'No registrada'}",
            "Estado del aplicativo: " + self._safe_excerpt(status, max_chars=1500),
            "",
            "--- Descripción del caso ---",
            str(description or "").strip(),
        ]
        max_chars = max(1000, int(getattr(settings, "ARANDA_MAX_DESCRIPTION_CHARS", 12000)))
        return "\n".join(lines)[:max_chars]

    # ------------------------------------------------------------------
    # Consulta, actualización, listado, notas y adjuntos
    # ------------------------------------------------------------------

    async def _get_case_with_session(
        self,
        client: httpx.AsyncClient,
        session: ArandaSession,
        *,
        item_id: Union[int, str],
        item_type: int,
        level: int,
    ) -> Dict[str, Any]:
        if item_type not in self.ITEM_TYPES:
            raise ArandaIntegrationError("Tipo de caso inválido.", code="InvalidItemType")
        if level not in self.DETAIL_LEVELS:
            raise ArandaIntegrationError("Nivel de detalle inválido.", code="InvalidLevelOfDetail")

        _, payload = await self._request(
            client,
            "GET",
            f"item/{item_id}/{item_type}/{session.user_id}",
            session_id=session.session_id,
            params={"level": level},
        )
        if not isinstance(payload, dict):
            raise ArandaIntegrationError(
                "La consulta del caso devolvió una estructura inesperada.",
                code="InvalidGetCaseResponse",
            )
        return payload

    async def get_case(
        self,
        item_id: Union[int, str],
        *,
        item_type: Optional[int] = None,
        level: int = 2,
    ) -> Dict[str, Any]:
        case_type = item_type or self._as_int(getattr(settings, "ARANDA_DEFAULT_ITEM_TYPE", 1), default=1)
        async with self._authenticated_session() as (client, session):
            return await self._get_case_with_session(
                client,
                session,
                item_id=item_id,
                item_type=case_type,
                level=level,
            )

    async def _list_history_with_session(
        self,
        client: httpx.AsyncClient,
        session: ArandaSession,
        *,
        item_id: Union[int, str],
        item_type: int,
        action_type_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Consulta el histórico reutilizando la sesión activa de Aranda."""
        if item_type not in self.ITEM_TYPES:
            raise ArandaIntegrationError("Tipo de caso inválido.", code="InvalidItemType")
        params = {"actionTypeId": action_type_id} if action_type_id is not None else None
        _, payload = await self._request(
            client,
            "GET",
            f"item/{item_id}/{item_type}/note/list",
            session_id=session.session_id,
            params=params,
        )
        if not isinstance(payload, list):
            raise ArandaIntegrationError(
                "El histórico devolvió una estructura inesperada.",
                code="InvalidHistoryResponse",
            )
        return [row for row in payload if isinstance(row, dict)]

    async def _list_files_with_session(
        self,
        client: httpx.AsyncClient,
        session: ArandaSession,
        *,
        item_id: Union[int, str],
        item_type: int,
    ) -> List[Dict[str, Any]]:
        """Consulta adjuntos reutilizando la sesión activa de Aranda."""
        if item_type not in self.ITEM_TYPES:
            raise ArandaIntegrationError("Tipo de caso inválido.", code="InvalidItemType")
        _, payload = await self._request(
            client,
            "GET",
            f"item/{item_id}/{item_type}/{session.user_id}/files",
            session_id=session.session_id,
        )
        if not isinstance(payload, list):
            raise ArandaIntegrationError(
                "El listado de adjuntos devolvió una estructura inesperada.",
                code="InvalidFileListResponse",
            )
        return [row for row in payload if isinstance(row, dict)]

    async def _search_users_with_session(
        self,
        client: httpx.AsyncClient,
        session: ArandaSession,
        *,
        project_id: int,
        field_name: str,
        value: str,
        comparison_operator_id: int = 5,
    ) -> List[Dict[str, Any]]:
        """Busca usuarios en Aranda para validar propiedad del ticket.

        Contrato ASDK: POST user/list con ProjectId y Criteria. Para correos y
        nombres de usuario se usa igualdad (5) por defecto; el caller puede usar
        LIKE (13) cuando sea necesario.
        """
        if project_id <= 0:
            raise ArandaIntegrationError("ProjectId inválido.", code="InvalidProjectId")
        if not str(field_name or "").strip() or not str(value or "").strip():
            return []

        body = {
            "ProjectId": project_id,
            "Criteria": [
                {
                    "ComparisonOperatorId": int(comparison_operator_id),
                    "FieldName": str(field_name).strip(),
                    "LogicOperatorId": 1,
                    "Value": str(value).strip(),
                }
            ],
        }
        _, payload = await self._request(
            client,
            "POST",
            "user/list",
            session_id=session.session_id,
            json_body=body,
        )
        if not isinstance(payload, dict):
            raise ArandaIntegrationError(
                "La búsqueda de usuarios devolvió una estructura inesperada.",
                code="InvalidUserListResponse",
            )
        data = payload.get("Data") or payload.get("data") or []
        if not isinstance(data, list):
            return []
        return [row for row in data if isinstance(row, dict)]

    async def search_users(
        self,
        *,
        project_id: Optional[int] = None,
        field_name: str,
        value: str,
        comparison_operator_id: int = 5,
    ) -> List[Dict[str, Any]]:
        project = project_id or self._as_int(
            getattr(settings, "ARANDA_PROJECT_ID", 0), default=0
        )
        async with self._authenticated_session() as (client, session):
            return await self._search_users_with_session(
                client,
                session,
                project_id=project,
                field_name=field_name,
                value=value,
                comparison_operator_id=comparison_operator_id,
            )

    async def get_ticket_tracking_bundle(
        self,
        *,
        item_candidates: Sequence[Union[int, str]],
        item_types: Sequence[int],
        level: int = 2,
        include_history: bool = True,
        include_files: bool = True,
        identity_email: Optional[str] = None,
        identity_username: Optional[str] = None,
        project_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Obtiene detalle, histórico, adjuntos y coincidencias de usuario.

        Todo se realiza dentro de UNA sesión ASDK para reducir consumo de
        licencias. Prueba los identificadores en el orden recibido (por ejemplo,
        primero el compuesto y luego el global) y los tipos permitidos.
        """
        candidates: List[Union[int, str]] = []
        for value in item_candidates:
            normalized: Union[int, str]
            if isinstance(value, int):
                normalized = value
            else:
                normalized = str(value or "").strip()
            if normalized not in ("", 0, None) and normalized not in candidates:
                candidates.append(normalized)

        types: List[int] = []
        for value in item_types:
            parsed = self._as_int(value, default=0)
            if parsed in self.ITEM_TYPES and parsed not in types:
                types.append(parsed)

        if not candidates:
            raise ArandaIntegrationError("No se recibió un identificador de caso.", code="InvalidItemId")
        if not types:
            raise ArandaIntegrationError("No se recibió un tipo de caso válido.", code="InvalidItemType")

        retryable_not_found = {
            "InvalidItemId",
            "InvalidItemType",
            "HTTP_404",
        }
        last_error: Optional[ArandaIntegrationError] = None

        async with self._authenticated_session() as (client, session):
            found_case: Optional[Dict[str, Any]] = None
            resolved_candidate: Optional[Union[int, str]] = None
            resolved_type: Optional[int] = None

            for item_type in types:
                for candidate in candidates:
                    try:
                        found_case = await self._get_case_with_session(
                            client,
                            session,
                            item_id=candidate,
                            item_type=item_type,
                            level=level,
                        )
                        resolved_candidate = candidate
                        resolved_type = item_type
                        break
                    except ArandaIntegrationError as exc:
                        last_error = exc
                        if exc.code not in retryable_not_found:
                            raise
                if found_case is not None:
                    break

            if found_case is None or resolved_type is None:
                raise last_error or ArandaIntegrationError(
                    "Caso no encontrado.", code="InvalidItemId", http_status=404
                )

            canonical_item_id: Union[int, str] = (
                self._as_positive_int(found_case.get("Id"))
                or self._as_positive_int(found_case.get("id"))
                or resolved_candidate
                or candidates[0]
            )

            history: List[Dict[str, Any]] = []
            files: List[Dict[str, Any]] = []
            history_error_code: Optional[str] = None
            files_error_code: Optional[str] = None

            if include_history:
                try:
                    history = await self._list_history_with_session(
                        client,
                        session,
                        item_id=canonical_item_id,
                        item_type=resolved_type,
                    )
                except ArandaIntegrationError as exc:
                    history_error_code = exc.code
                    logger.warning(
                        "aranda_tracking_history_failed",
                        item_id=str(canonical_item_id),
                        item_type=resolved_type,
                        error_code=exc.code,
                    )

            if include_files:
                try:
                    files = await self._list_files_with_session(
                        client,
                        session,
                        item_id=canonical_item_id,
                        item_type=resolved_type,
                    )
                except ArandaIntegrationError as exc:
                    files_error_code = exc.code
                    logger.warning(
                        "aranda_tracking_files_failed",
                        item_id=str(canonical_item_id),
                        item_type=resolved_type,
                        error_code=exc.code,
                    )

            resolved_project = (
                self._as_positive_int(found_case.get("ProjectId"))
                or self._as_positive_int(project_id)
                or self._as_positive_int(getattr(settings, "ARANDA_PROJECT_ID", 0))
            )
            user_matches: List[Dict[str, Any]] = []
            seen_user_ids: set[int] = set()

            async def add_matches(field_name: str, value: Optional[str]) -> None:
                if not value or not resolved_project:
                    return
                try:
                    rows = await self._search_users_with_session(
                        client,
                        session,
                        project_id=resolved_project,
                        field_name=field_name,
                        value=value,
                        comparison_operator_id=5,
                    )
                except ArandaIntegrationError as exc:
                    logger.warning(
                        "aranda_tracking_user_lookup_failed",
                        project_id=resolved_project,
                        field_name=field_name,
                        error_code=exc.code,
                    )
                    return
                for row in rows:
                    user_id = self._as_positive_int(row.get("Id") or row.get("id"))
                    if user_id and user_id not in seen_user_ids:
                        seen_user_ids.add(user_id)
                        # Solo se devuelven campos mínimos para la validación.
                        user_matches.append(
                            {
                                "Id": user_id,
                                "Email": row.get("Email") or row.get("email"),
                                "UserName": row.get("UserName") or row.get("username"),
                                "Name": row.get("Name") or row.get("name"),
                            }
                        )

            await add_matches("Email", identity_email)
            await add_matches("UserName", identity_username)

            return {
                "case": found_case,
                "history": history,
                "files": files,
                "user_matches": user_matches,
                "resolved_item_id": canonical_item_id,
                "resolved_item_type": resolved_type,
                "history_error_code": history_error_code,
                "files_error_code": files_error_code,
            }

    async def update_case(
        self,
        item_id: Union[int, str],
        fields: Mapping[str, Any],
        *,
        item_type: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not fields:
            raise ArandaIntegrationError("No se enviaron campos para actualizar.", code="EmptyUpdate")

        invalid = [name for name in fields if str(name).strip().lower() in self._PROTECTED_UPDATE_FIELDS]
        if invalid:
            raise ArandaIntegrationError(
                "La actualización contiene campos no editables: " + ", ".join(invalid),
                code="ProtectedArandaField",
            )

        body = [self._field(str(name).strip(), value) for name, value in fields.items() if value is not None]
        case_type = item_type or self._as_int(getattr(settings, "ARANDA_DEFAULT_ITEM_TYPE", 1), default=1)
        if case_type not in self.ITEM_TYPES:
            raise ArandaIntegrationError("Tipo de caso inválido.", code="InvalidItemType")

        async with self._authenticated_session() as (client, session):
            _, payload = await self._request(
                client,
                "POST",
                f"item/update/{item_id}/{case_type}/{session.user_id}",
                session_id=session.session_id,
                json_body=body,
            )
            mapped = self._field_values_to_dict(payload)
            return {
                "updated": self._as_bool(mapped.get("result")),
                "item_id": self._as_positive_int(mapped.get("itemid")),
                "composed_item_id": mapped.get("composeditemid"),
                "is_closed": self._as_bool(mapped.get("isclosed")),
            }

    async def list_cases(
        self,
        *,
        project_id: Optional[int] = None,
        criteria: Optional[Sequence[Mapping[str, Any]]] = None,
        where_criteria: Optional[Sequence[Mapping[str, Any]]] = None,
        start: int = 1,
        page_size: int = 50,
        view_id: Optional[int] = None,
        order_column: str = "RegistrationDate",
        descending: bool = True,
    ) -> Dict[str, Any]:
        maximum = max(1, int(getattr(settings, "ARANDA_MAX_PAGE_SIZE", 50)))
        size = min(max(1, page_size), maximum)
        start = max(1, start)
        end = start + size - 1

        body = {
            "Paging": {"Start": start, "End": end, "Size": 0},
            "Criteria": list(criteria or []),
            "WhereCriteria": list(where_criteria or []),
            "Order": {"ColumnName": order_column, "ModeId": 2 if descending else 1},
            "ViewId": view_id or self._as_int(getattr(settings, "ARANDA_LIST_VIEW_ID", 5), default=5),
            "ProjectId": project_id
            or self._as_int(getattr(settings, "ARANDA_PROJECT_ID", 0), default=0),
        }

        async with self._authenticated_session() as (client, session):
            _, payload = await self._request(
                client,
                "POST",
                "item/list",
                session_id=session.session_id,
                json_body=body,
            )
            if not isinstance(payload, dict):
                raise ArandaIntegrationError(
                    "El listado de casos devolvió una estructura inesperada.",
                    code="InvalidListCasesResponse",
                )
            return payload

    async def add_note(
        self,
        item_id: Union[int, str],
        description: str,
        *,
        item_type: Optional[int] = None,
        is_private: bool = False,
    ) -> JsonValue:
        if not str(description or "").strip():
            raise ArandaIntegrationError("La nota no puede estar vacía.", code="EmptyNote")
        case_type = item_type or self._as_int(getattr(settings, "ARANDA_DEFAULT_ITEM_TYPE", 1), default=1)

        async with self._authenticated_session() as (client, session):
            _, payload = await self._request(
                client,
                "POST",
                f"item/{item_id}/{case_type}/note",
                session_id=session.session_id,
                json_body={"Description": description.strip(), "IsPrivate": bool(is_private)},
            )
            return payload

    async def list_history(
        self,
        item_id: Union[int, str],
        *,
        item_type: Optional[int] = None,
        action_type_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        case_type = item_type or self._as_int(getattr(settings, "ARANDA_DEFAULT_ITEM_TYPE", 1), default=1)
        params = {"actionTypeId": action_type_id} if action_type_id is not None else None

        async with self._authenticated_session() as (client, session):
            _, payload = await self._request(
                client,
                "GET",
                f"item/{item_id}/{case_type}/note/list",
                session_id=session.session_id,
                params=params,
            )
            if not isinstance(payload, list):
                raise ArandaIntegrationError(
                    "El histórico devolvió una estructura inesperada.",
                    code="InvalidHistoryResponse",
                )
            return [row for row in payload if isinstance(row, dict)]

    async def list_files(
        self,
        item_id: Union[int, str],
        *,
        item_type: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        case_type = item_type or self._as_int(getattr(settings, "ARANDA_DEFAULT_ITEM_TYPE", 1), default=1)
        async with self._authenticated_session() as (client, session):
            _, payload = await self._request(
                client,
                "GET",
                f"item/{item_id}/{case_type}/{session.user_id}/files",
                session_id=session.session_id,
            )
            if not isinstance(payload, list):
                raise ArandaIntegrationError(
                    "El listado de adjuntos devolvió una estructura inesperada.",
                    code="InvalidFileListResponse",
                )
            return [row for row in payload if isinstance(row, dict)]

    async def attach_file(
        self,
        item_id: Union[int, str],
        file_path: Union[str, Path],
        *,
        item_type: Optional[int] = None,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        path = Path(file_path)
        if not path.is_file():
            raise ArandaIntegrationError("El archivo adjunto no existe.", code="AttachmentNotFound")

        max_bytes = max(1, int(getattr(settings, "ARANDA_MAX_ATTACHMENT_BYTES", 10 * 1024 * 1024)))
        if path.stat().st_size > max_bytes:
            raise ArandaIntegrationError(
                "El archivo supera el tamaño máximo permitido por BOTIQ.",
                code="AttachmentTooLarge",
            )

        case_type = item_type or self._as_int(getattr(settings, "ARANDA_DEFAULT_ITEM_TYPE", 1), default=1)
        resolved_name = filename or path.name
        resolved_type = content_type or mimetypes.guess_type(resolved_name)[0] or "application/octet-stream"

        async with self._authenticated_session() as (client, session):
            with path.open("rb") as handle:
                files = {"file0": (resolved_name, handle, resolved_type)}
                data = {
                    "itemId": str(item_id),
                    "itemType": str(case_type),
                    "userId": str(session.user_id),
                }
                _, payload = await self._request(
                    client,
                    "POST",
                    "item/addfile",
                    session_id=session.session_id,
                    data=data,
                    files=files,
                )

            if not isinstance(payload, list):
                raise ArandaIntegrationError(
                    "La carga del adjunto devolvió una estructura inesperada.",
                    code="InvalidAttachmentResponse",
                )
            return [row for row in payload if isinstance(row, dict)]

    async def list_categories(
        self,
        *,
        project_id: Optional[int] = None,
        item_type: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        project = project_id or self._as_int(getattr(settings, "ARANDA_PROJECT_ID", 0), default=0)
        case_type = item_type or self._as_int(getattr(settings, "ARANDA_DEFAULT_ITEM_TYPE", 1), default=1)
        async with self._authenticated_session() as (client, session):
            _, payload = await self._request(
                client,
                "GET",
                f"project/{project}/{case_type}/category/list",
                session_id=session.session_id,
            )
            if not isinstance(payload, list):
                raise ArandaIntegrationError(
                    "El listado de categorías devolvió una estructura inesperada.",
                    code="InvalidCategoryListResponse",
                )
            return [row for row in payload if isinstance(row, dict)]

    async def list_services(
        self,
        *,
        project_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        project = project_id or self._as_int(getattr(settings, "ARANDA_PROJECT_ID", 0), default=0)
        async with self._authenticated_session() as (client, session):
            _, payload = await self._request(
                client,
                "POST",
                f"project/{project}/services",
                session_id=session.session_id,
                json_body=None,
            )
            if not isinstance(payload, list):
                raise ArandaIntegrationError(
                    "El listado de servicios devolvió una estructura inesperada.",
                    code="InvalidServiceListResponse",
                )
            return [row for row in payload if isinstance(row, dict)]

    async def list_services_by_category(
        self,
        category_id: int,
        *,
        parameter_id: int,
        entity_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        if parameter_id not in {1, 2, 3}:
            raise ArandaIntegrationError(
                "parameter_id debe ser 1=cliente, 2=compañía o 3=CI.",
                code="InvalidParameterId",
            )
        params: Dict[str, Any] = {"paramId": parameter_id}
        if entity_id is not None:
            params["entityId"] = entity_id

        async with self._authenticated_session() as (client, session):
            _, payload = await self._request(
                client,
                "GET",
                f"category/{category_id}/services",
                session_id=session.session_id,
                params=params,
            )
            if not isinstance(payload, list):
                raise ArandaIntegrationError(
                    "El listado de servicios por categoría devolvió una estructura inesperada.",
                    code="InvalidCategoryServiceResponse",
                )
            return [row for row in payload if isinstance(row, dict)]

    # ------------------------------------------------------------------
    # Persistencia sobre el modelo Conversation existente
    # ------------------------------------------------------------------

    def build_ticket_description(self, conversation: Conversation, last_user_message: str) -> str:
        """Mantiene la firma usada por el flujo actual de BOTIQ."""
        metadata = conversation.metadata_ or {}
        case = metadata.get("case") if isinstance(metadata, dict) else {}
        slots = case.get("slots") if isinstance(case, dict) else {}
        return (
            "Caso generado desde BOTIQ únicamente después de agotar las opciones de autoservicio.\n\n"
            f"Perfil seleccionado: {conversation.selected_profile or 'No disponible'}\n"
            f"Sesión: {conversation.session_id or 'No disponible'}\n"
            f"Conversación: {conversation.id}\n"
            f"Preguntas realizadas: {conversation.question_count or 0}\n"
            f"Intentos de solución agotados: {conversation.resolution_attempts or 0}\n"
            f"URL detectada: {conversation.detected_url or 'No registrada'}\n"
            f"IP detectada: {conversation.detected_ip or 'No registrada'}\n"
            f"Datos estructurados del caso: {self._safe_excerpt(slots, 2500)}\n"
            f"Estado aplicativo: {self._safe_excerpt(conversation.application_status_snapshot, 1500)}\n\n"
            f"Última solicitud del usuario:\n{last_user_message}"
        )

    def mark_ticket_result(self, conversation: Conversation, result: Dict[str, Any]) -> None:
        """
        Guarda resultado y trazabilidad usando las columnas existentes y JSONB.

        ``aranda_ticket_created_at`` solo se llena si Aranda confirmó la creación.
        Para fallos/timeout se registra ``last_attempted_at`` en metadata_, evitando
        afirmar que un ticket fue creado cuando no existe confirmación.
        """
        now = datetime.now(timezone.utc)
        created = bool(result.get("created"))

        if result.get("ticket_id"):
            conversation.aranda_ticket_id = str(result["ticket_id"])
        conversation.aranda_ticket_status = str(result.get("status") or "")[:100]
        conversation.escalated_to_aranda = created
        if created:
            conversation.aranda_ticket_created_at = now

        metadata = dict(conversation.metadata_ or {})
        previous = metadata.get("aranda")
        previous = dict(previous) if isinstance(previous, dict) else {}
        attempt_count = int(previous.get("attempt_count") or 0) + 1

        tracking = {
            **previous,
            "attempt_count": attempt_count,
            "last_attempted_at": now.isoformat(),
            "status": result.get("status"),
            "created": created,
            "ticket_id": result.get("ticket_id"),
            "item_id": result.get("item_id"),
            "composed_item_id": result.get("composed_item_id"),
            "item_type": result.get("item_type"),
            "correlation_id": result.get("correlation_id"),
            "error_code": result.get("error_code"),
            "http_status": result.get("http_status"),
            "requires_reconciliation": bool(result.get("requires_reconciliation")),
            "verification": result.get("verification"),
        }
        if created:
            tracking["created_at"] = now.isoformat()

        metadata["aranda"] = tracking
        conversation.metadata_ = metadata


aranda_service = ArandaService()
