from __future__ import annotations

import html
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.roles import UserRole
from app.models.conversation import Conversation
from app.models.user import User
from app.services.aranda_service import ArandaIntegrationError, aranda_service


logger = get_logger(__name__, service="aranda_tracking")


@dataclass(frozen=True)
class TicketReference:
    raw: str
    normalized: str
    prefix: Optional[str]
    composed_id: Optional[str]
    global_id: Optional[int]
    project_id: Optional[int]
    id_by_project: Optional[int]
    item_type: Optional[int]

    @property
    def candidates(self) -> List[Union[str, int]]:
        values: List[Union[str, int]] = []
        if self.composed_id:
            values.append(self.composed_id)
        if self.global_id:
            values.append(self.global_id)
        return values


class ArandaTrackingService:
    """Detecta intención, valida acceso y formatea seguimiento sin usar IA."""

    PREFIX_TO_ITEM_TYPE = {"IM": 1, "PM": 2, "CHG": 3, "RF": 4}
    FULL_REFERENCE_RE = re.compile(
        r"\b(?P<prefix>IM|PM|CHG|RF)-(?P<global>\d+)-(?P<project>\d+)-(?P<project_item>\d+)\b",
        re.IGNORECASE,
    )
    NUMERIC_REFERENCE_RE = re.compile(r"(?<!\d)(?P<id>\d{4,12})(?!\d)")
    TRACKING_PHRASES = (
        "seguimiento",
        "consultar ticket",
        "consultar caso",
        "estado del ticket",
        "estado del caso",
        "como va mi ticket",
        "cómo va mi ticket",
        "como va el ticket",
        "cómo va el ticket",
        "ver ticket",
        "ver caso",
        "ultima novedad",
        "última novedad",
        "ultimas novedades",
        "últimas novedades",
        "historial del ticket",
        "historico del ticket",
        "histórico del ticket",
        "movimientos del ticket",
    )

    ACTION_LABELS = {
        "ADD ATTACHMENT": "Archivo adjunto agregado",
        "DELETE ATTACHMENT": "Archivo adjunto eliminado",
        "REMOVE ATTACHMENT": "Archivo adjunto eliminado",
        "ATTACH FILE": "Archivo adjunto agregado",
        "ADD FILE": "Archivo adjunto agregado",
        "UPLOAD FILE": "Archivo adjunto agregado",
        "CREATE ITEM": "Ticket creado",
        "REGISTER ITEM": "Ticket registrado",
        "UPDATE ITEM": "Ticket actualizado",
        "EDIT ITEM": "Ticket actualizado",
        "ASSIGN ITEM": "Ticket asignado",
        "REASSIGN ITEM": "Ticket reasignado",
        "CHANGE STATE": "Cambio de estado",
        "CHANGE STATUS": "Cambio de estado",
        "ADD NOTE": "Nota agregada",
        "CREATE NOTE": "Nota agregada",
        "NOTE": "Nota agregada",
        "NOTA": "Nota agregada",
        "CLOSE ITEM": "Ticket cerrado",
        "REOPEN ITEM": "Ticket reabierto",
        "SOLUTION ITEM": "Solución registrada",
        "RESOLVE ITEM": "Ticket resuelto",
    }

    ATTACHMENT_ACTIONS = {
        "ADD ATTACHMENT",
        "DELETE ATTACHMENT",
        "REMOVE ATTACHMENT",
        "ATTACH FILE",
        "ADD FILE",
        "UPLOAD FILE",
    }

    MONTHS_ES = (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )

    def is_tracking_request(self, message: str) -> bool:
        text = self._normalize_text(message)
        if not text:
            return False
        has_full = bool(self.FULL_REFERENCE_RE.search(message or ""))
        has_tracking_phrase = any(phrase in text for phrase in self.TRACKING_PHRASES)
        # Un código compuesto enviado solo también se interpreta como consulta.
        only_reference = bool(
            has_full
            and self.FULL_REFERENCE_RE.sub("", message or "").strip(" .,:;!?-\t\n") == ""
        )
        return bool(has_tracking_phrase or only_reference)

    def extract_reference(self, message: str) -> Optional[TicketReference]:
        full = self.FULL_REFERENCE_RE.search(message or "")
        if full:
            prefix = full.group("prefix").upper()
            composed = full.group(0).upper()
            return TicketReference(
                raw=full.group(0),
                normalized=composed,
                prefix=prefix,
                composed_id=composed,
                global_id=int(full.group("global")),
                project_id=int(full.group("project")),
                id_by_project=int(full.group("project_item")),
                item_type=self.PREFIX_TO_ITEM_TYPE.get(prefix),
            )

        numeric = self.NUMERIC_REFERENCE_RE.search(message or "")
        if numeric:
            value = int(numeric.group("id"))
            return TicketReference(
                raw=numeric.group(0),
                normalized=str(value),
                prefix=None,
                composed_id=None,
                global_id=value,
                project_id=None,
                id_by_project=None,
                item_type=None,
            )
        return None

    async def track_message(
        self,
        *,
        message: str,
        conversation: Conversation,
        current_user: User,
    ) -> Dict[str, Any]:
        reference = self.extract_reference(message)
        if not reference:
            return {
                "handled": True,
                "ok": False,
                "status": "reference_required",
                "audit_action": "aranda_tracking_requested",
                "message": (
                    "Para consultar el seguimiento necesito el número completo del ticket. "
                    "Por ejemplo: **RF-886064-1-674642**."
                ),
                "safe_metadata": {"status": "reference_required"},
            }

        if not bool(getattr(settings, "ARANDA_TRACKING_ENABLED", True)):
            return self._safe_failure(
                reference,
                status="tracking_disabled",
                audit_action="aranda_tracking_error",
                message="El seguimiento de tickets no está habilitado en este momento.",
            )

        if not aranda_service.is_connection_configured():
            report = aranda_service.connection_report()
            return self._safe_failure(
                reference,
                status="invalid_configuration",
                audit_action="aranda_tracking_error",
                message=(
                    "La conexión con Aranda todavía no está completamente configurada. "
                    "Contacta al administrador de BOTIQ."
                ),
                extra={"configuration_valid": bool(report.get("valid"))},
            )

        item_types = self._item_types_for(reference)
        username = self._identity_username(conversation, current_user)

        try:
            bundle = await aranda_service.get_ticket_tracking_bundle(
                item_candidates=reference.candidates,
                item_types=item_types,
                level=2,
                include_history=True,
                include_files=True,
                identity_email=getattr(current_user, "email", None),
                identity_username=username,
                project_id=reference.project_id,
            )
        except ArandaIntegrationError as exc:
            if exc.code in {"InvalidItemId", "HTTP_404"}:
                return self._safe_failure(
                    reference,
                    status="not_found",
                    audit_action="aranda_tracking_not_found",
                    message=(
                        f"No encontré el ticket **{reference.normalized}** o la cuenta técnica "
                        "no tiene permiso para consultarlo. Verifica el número e inténtalo nuevamente."
                    ),
                    extra={"error_code": exc.code},
                )
            if exc.code.startswith("Unauthorized") or exc.http_status == 403:
                return self._safe_failure(
                    reference,
                    status="aranda_permission_denied",
                    audit_action="aranda_tracking_denied",
                    message=(
                        "La cuenta técnica de BOTIQ no tiene permisos para consultar ese tipo de caso "
                        "o proyecto en Aranda."
                    ),
                    extra={"error_code": exc.code},
                )
            return self._safe_failure(
                reference,
                status="aranda_error",
                audit_action="aranda_tracking_error",
                message=(
                    "No fue posible consultar Aranda en este momento. "
                    "La consulta no creó ni modificó ningún ticket."
                ),
                extra={"error_code": exc.code, "http_status": exc.http_status},
            )
        except Exception as exc:  # defensa final; no exponer detalles internos
            logger.exception(
                "aranda_tracking_unexpected_error",
                reference=reference.normalized,
                exception_type=type(exc).__name__,
            )
            return self._safe_failure(
                reference,
                status="unexpected_error",
                audit_action="aranda_tracking_error",
                message=(
                    "No fue posible completar el seguimiento en este momento. "
                    "La consulta fue únicamente de lectura."
                ),
                extra={"exception_type": type(exc).__name__},
            )

        case = bundle.get("case") or {}
        access_ok, access_reason = self._validate_access(
            current_user=current_user,
            conversation=conversation,
            reference=reference,
            case=case,
            user_matches=bundle.get("user_matches") or [],
        )
        if not access_ok:
            return self._safe_failure(
                reference,
                status="ownership_denied",
                audit_action="aranda_tracking_denied",
                message=access_reason,
                extra={
                    "resolved_item_id": bundle.get("resolved_item_id"),
                    "resolved_item_type": bundle.get("resolved_item_type"),
                },
            )

        history = self._filter_history(bundle.get("history") or [], current_user.role)
        files = self._filter_files(bundle.get("files") or [], current_user.role)
        history_limit = max(1, int(getattr(settings, "ARANDA_TRACKING_HISTORY_LIMIT", 5)))
        file_limit = max(0, int(getattr(settings, "ARANDA_TRACKING_FILE_LIMIT", 10)))

        # Los eventos de adjuntos se muestran en una sección propia. Excluirlos
        # del histórico evita repetir el mismo archivo dos veces en la respuesta.
        history = [row for row in history if not self._is_attachment_history(row)]
        history = self._sort_history(history)[:history_limit]
        files = files[:file_limit]

        display_reference = str(
            case.get("ComposedId")
            or case.get("composedId")
            or reference.composed_id
            or bundle.get("resolved_item_id")
            or reference.normalized
        )
        response_text = self._format_response(
            display_reference=display_reference,
            case=case,
            history=history,
            files=files,
            history_error=bool(bundle.get("history_error_code")),
            files_error=bool(bundle.get("files_error_code")),
        )

        safe_summary = {
            "reference": display_reference,
            "item_id": bundle.get("resolved_item_id"),
            "item_type": bundle.get("resolved_item_type"),
            "state_name": case.get("StateName"),
            "is_closed": self._bool_value(case.get("IsClosed")),
            "project_id": case.get("ProjectId"),
            "history_items_shown": len(history),
            "files_shown": len(files),
            "status": "success",
        }
        return {
            "handled": True,
            "ok": True,
            "status": "success",
            "audit_action": "aranda_tracking_success",
            "message": response_text,
            "safe_metadata": safe_summary,
            "ticket_tracking": safe_summary,
        }

    def _validate_access(
        self,
        *,
        current_user: User,
        conversation: Conversation,
        reference: TicketReference,
        case: Dict[str, Any],
        user_matches: Sequence[Dict[str, Any]],
    ) -> Tuple[bool, str]:
        project_id = self._positive_int(case.get("ProjectId")) or reference.project_id
        allowed_projects = self._allowed_project_ids()
        if not allowed_projects:
            return False, (
                "No hay proyectos de Aranda autorizados para seguimiento en BOTIQ. "
                "El administrador debe configurar ARANDA_TRACKING_ALLOWED_PROJECT_IDS "
                "o ARANDA_PROJECT_ID."
            )
        if project_id not in allowed_projects:
            return False, (
                "El ticket pertenece a un proyecto que no está autorizado para consulta desde BOTIQ."
            )

        role = current_user.role
        if role in {UserRole.ADMIN, UserRole.SUPPORT_ENGINEER}:
            return True, "Acceso autorizado por rol y proyecto."

        # Un empleado puede consultar siempre el ticket creado dentro de su
        # propia conversación autenticada.
        local_ticket = str(conversation.aranda_ticket_id or "").strip().upper()
        identifiers = {
            str(reference.normalized).strip().upper(),
            str(case.get("ComposedId") or "").strip().upper(),
            str(case.get("Id") or "").strip().upper(),
        }
        identifiers.discard("")
        if local_ticket and local_ticket in identifiers:
            return True, "Ticket asociado a la conversación del usuario."

        if not bool(getattr(settings, "ARANDA_TRACKING_EMPLOYEE_REQUIRE_OWNERSHIP", True)):
            return True, "La política permite consulta de empleados sin validación de propiedad."

        allowed_user_ids = {
            self._positive_int(row.get("Id") or row.get("id"))
            for row in user_matches
        }
        allowed_user_ids.discard(None)
        case_owner_ids = {
            self._positive_int(case.get("CustomerId")),
            self._positive_int(case.get("AuthorId")),
        }
        case_owner_ids.discard(None)

        if allowed_user_ids and allowed_user_ids.intersection(case_owner_ids):
            return True, "El usuario autenticado coincide con el cliente o autor del caso."

        return False, (
            "No fue posible validar que este ticket esté asociado a tu usuario. "
            "Por seguridad, un empleado solo puede consultar sus propios casos. "
            "Solicita apoyo a la Mesa de Servicio si necesitas revisar un ticket de otra persona."
        )

    def _filter_history(self, rows: Iterable[Dict[str, Any]], role: UserRole) -> List[Dict[str, Any]]:
        if role == UserRole.ADMIN:
            show_private = bool(
                getattr(settings, "ARANDA_TRACKING_SHOW_PRIVATE_NOTES_TO_ADMIN", True)
            )
        elif role == UserRole.SUPPORT_ENGINEER:
            show_private = bool(
                getattr(settings, "ARANDA_TRACKING_SHOW_PRIVATE_NOTES_TO_SUPPORT", False)
            )
        else:
            show_private = False

        result: List[Dict[str, Any]] = []
        for row in rows:
            if self._bool_value(row.get("IsPrivate")) and not show_private:
                continue
            result.append(
                {
                    "ActionName": row.get("ActionName"),
                    "ActionType": row.get("ActionType"),
                    "AuthorName": row.get("AuthorName"),
                    "CreationDate": row.get("CreationDate"),
                    "Description": self._clean_text(row.get("Description"), 600),
                    "IsPrivate": self._bool_value(row.get("IsPrivate")),
                    "AfterClosed": self._bool_value(row.get("AfterClosed")),
                }
            )
        return result

    def _filter_files(self, rows: Iterable[Dict[str, Any]], role: UserRole) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for row in rows:
            is_public = self._bool_value(row.get("IsPublic"))
            if role == UserRole.EMPLOYEE and not is_public:
                continue
            # Deliberadamente NO se devuelve Url: Aranda incluye un token en la
            # URL de descarga y no debe persistirse ni mostrarse en el chat.
            result.append(
                {
                    "Name": self._clean_text(row.get("Name"), 200),
                    "Size": self._positive_int(row.get("Size")) or 0,
                    "Created": row.get("Created"),
                    "IsPublic": is_public,
                }
            )
        return result

    def _format_response(
        self,
        *,
        display_reference: str,
        case: Dict[str, Any],
        history: Sequence[Dict[str, Any]],
        files: Sequence[Dict[str, Any]],
        history_error: bool,
        files_error: bool,
    ) -> str:
        state = self._clean_text(case.get("StateName"), 120) or "Estado no informado"
        is_closed = self._bool_value(case.get("IsClosed"))
        status_summary = f"{state} · {'Cerrado' if is_closed else 'Abierto'}"

        subject = self._clean_text(case.get("Subject"), 300)
        service = self._clean_text(case.get("ServiceName"), 180)
        category = self._clean_text(case.get("CategoryName"), 180)
        group = self._clean_text(case.get("GroupName"), 180)
        specialist = self._clean_text(case.get("SpecialistName"), 180)
        priority = self._humanize_level(case.get("PriorityName"))
        urgency = self._humanize_level(case.get("UrgencyName"))
        progress = self._progress(case.get("Progress"))

        registered_at = self._format_date_long(case.get("RegistrationDate"))
        expected_solution = self._format_date_long(
            case.get("SolutionDateExpected")
            or self._nested(case, "SolutionDate", "Expected")
        )
        closed_at = self._format_date_long(
            case.get("ClosedDate")
            or case.get("SolutionDateReal")
            or self._nested(case, "SolutionDate", "Real")
        )

        lines = [
            f"🎫 **Ticket {display_reference}**",
            "",
            f"**{status_summary}**",
        ]

        summary_fields = [
            ("Asunto", subject),
            ("Servicio", service),
            ("Categoría", category),
        ]
        if any(value for _, value in summary_fields):
            lines.extend(["", "### Resumen"])
            for label, value in summary_fields:
                if value:
                    lines.append(f"**{label}:** {value}")

        attention_fields = [
            ("Grupo responsable", group),
            ("Especialista responsable", specialist),
            ("Prioridad", priority),
            ("Urgencia", urgency),
            ("Avance reportado por Aranda", progress),
        ]
        if any(value for _, value in attention_fields):
            lines.extend(["", "### Atención del caso"])
            for label, value in attention_fields:
                if value:
                    lines.append(f"**{label}:** {value}")

        date_fields = [
            ("Registrado", registered_at),
            ("Fecha estimada de solución", expected_solution),
            ("Fecha de cierre", closed_at if is_closed else None),
        ]
        if any(value for _, value in date_fields):
            lines.extend(["", "### Fechas"])
            for label, value in date_fields:
                if value:
                    lines.append(f"**{label}:** {value}")

        lines.extend(["", "### Últimas novedades"])
        if history:
            for index, row in enumerate(history, start=1):
                date = self._format_date_long(row.get("CreationDate")) or "Fecha no informada"
                action = self._translate_action(row.get("ActionName"))
                author = self._clean_text(row.get("AuthorName"), 120) or "Aranda Service Desk"
                description = self._humanize_history_description(row)
                lines.extend(
                    [
                        "",
                        f"**{index}. {date}**",
                        f"**{action}**",
                        description,
                        f"_Registrado por: {author}_",
                    ]
                )
        elif history_error:
            lines.append(
                "No fue posible consultar el histórico, aunque el estado actual del ticket sí está disponible."
            )
        elif files:
            lines.append(
                "No hay actualizaciones públicas adicionales; los archivos asociados se muestran a continuación."
            )
        else:
            lines.append("No hay movimientos públicos disponibles para mostrar.")

        lines.extend(["", "### Archivos adjuntos"])
        if files:
            for row in files:
                name = self._clean_text(row.get("Name"), 200) or "Archivo"
                size = self._human_size(row.get("Size"))
                created = self._format_date_long(row.get("Created"))
                lines.append("")
                lines.append(f"📎 **{name}**")
                if size:
                    lines.append(f"Tamaño: {size}")
                if created:
                    lines.append(f"Adjuntado: {created}")
            lines.extend(
                [
                    "",
                    "Por seguridad, BOTIQ no publica en el chat los enlaces temporales de descarga de Aranda.",
                ]
            )
        elif files_error:
            lines.append("No fue posible consultar los archivos adjuntos en esta respuesta.")
        else:
            lines.append("No hay archivos adjuntos públicos disponibles.")

        lines.extend(
            [
                "",
                "🔒 Esta consulta fue únicamente informativa. BOTIQ no modificó el ticket ni publicó información privada de Aranda.",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def _normalize_action(cls, value: Any) -> str:
        action = cls._clean_text(value, 100).upper()
        action = action.replace("_", " ").replace("-", " ")
        return " ".join(action.split())

    @classmethod
    def _translate_action(cls, value: Any) -> str:
        action = cls._normalize_action(value)
        if not action:
            return "Actualización del ticket"
        return cls.ACTION_LABELS.get(action, action.title())

    @classmethod
    def _is_attachment_history(cls, row: Dict[str, Any]) -> bool:
        action = cls._normalize_action(row.get("ActionName"))
        if action in cls.ATTACHMENT_ACTIONS:
            return True
        description = cls._clean_text(row.get("Description"), 300).lower()
        return "filename:" in description and "attachment" in action.lower()

    @classmethod
    def _humanize_history_description(cls, row: Dict[str, Any]) -> str:
        action = cls._normalize_action(row.get("ActionName"))
        description = cls._clean_text(row.get("Description"), 600)

        if action in {"CREATE ITEM", "REGISTER ITEM"}:
            return "El requerimiento fue registrado correctamente en Aranda."
        if action in {"CLOSE ITEM", "RESOLVE ITEM", "SOLUTION ITEM"}:
            return description or "Aranda registró la solución o cierre del ticket."
        if action == "REOPEN ITEM":
            return description or "El ticket fue reabierto para continuar su gestión."
        if action in {"ASSIGN ITEM", "REASSIGN ITEM"}:
            return description or "El ticket fue asignado a un responsable de atención."
        if action in {"CHANGE STATE", "CHANGE STATUS"}:
            return description or "Aranda registró un cambio en el estado del ticket."
        if action in {"ADD NOTE", "CREATE NOTE", "NOTE", "NOTA"}:
            return description or "Se agregó una nueva nota pública al ticket."

        if description:
            replacements = {
                "Filename:": "Archivo:",
                "File name:": "Archivo:",
                "Size:": "Tamaño:",
                "Service Request registered:": "Requerimiento registrado:",
                "Incident registered:": "Incidente registrado:",
            }
            for original, translated in replacements.items():
                description = re.sub(
                    re.escape(original),
                    translated,
                    description,
                    flags=re.IGNORECASE,
                )
            return description

        return "Movimiento registrado sin detalle público."

    def _item_types_for(self, reference: TicketReference) -> List[int]:
        if reference.item_type:
            return [reference.item_type]
        configured = str(getattr(settings, "ARANDA_TRACKING_TRY_ITEM_TYPES", "4,1,2,3"))
        values: List[int] = []
        for raw in configured.split(","):
            parsed = self._positive_int(raw)
            if parsed in {1, 2, 3, 4} and parsed not in values:
                values.append(parsed)
        return values or [4, 1, 2, 3]

    def _allowed_project_ids(self) -> set[int]:
        raw = str(getattr(settings, "ARANDA_TRACKING_ALLOWED_PROJECT_IDS", "") or "")
        result = {
            value
            for value in (self._positive_int(part) for part in raw.split(","))
            if value
        }
        if not result:
            configured = self._positive_int(getattr(settings, "ARANDA_PROJECT_ID", 0))
            if configured:
                result.add(configured)
        return result

    @staticmethod
    def _identity_username(conversation: Conversation, current_user: User) -> Optional[str]:
        if conversation.support_network_username:
            return conversation.support_network_username
        email = str(getattr(current_user, "email", "") or "").strip()
        return email.split("@", 1)[0] if "@" in email else (email or None)

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"true", "1", "yes", "si", "sí"}

    @staticmethod
    def _positive_int(value: Any) -> Optional[int]:
        try:
            parsed = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @staticmethod
    def _nested(data: Dict[str, Any], key: str, child: str) -> Any:
        value = data.get(key)
        return value.get(child) if isinstance(value, dict) else None

    @staticmethod
    def _clean_text(value: Any, max_chars: int) -> str:
        text = str(value or "")
        text = re.sub(
            r"<(script|style)\b[^>]*>.*?</\1>",
            " ",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"</?(p|div|li|ul|ol|tr|td|th)\b[^>]*>", " ", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text).replace("\xa0", " ")
        text = " ".join(text.split())
        return text[:max_chars]

    @staticmethod
    def _normalize_text(value: str) -> str:
        lowered = str(value or "").strip().lower()
        normalized = unicodedata.normalize("NFKD", lowered)
        return "".join(char for char in normalized if not unicodedata.combining(char))

    @staticmethod
    def _progress(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        return f"{number:g} %"

    @classmethod
    def _humanize_level(cls, value: Any) -> Optional[str]:
        normalized = cls._normalize_text(cls._clean_text(value, 80)).upper()
        labels = {
            "BAJO": "Baja",
            "BAJA": "Baja",
            "MEDIO": "Media",
            "MEDIA": "Media",
            "ALTO": "Alta",
            "ALTA": "Alta",
            "CRITICO": "Crítica",
            "CRITICA": "Crítica",
            "URGENTE": "Urgente",
        }
        return labels.get(normalized, cls._clean_text(value, 80).title() or None)

    @staticmethod
    def _format_date(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        text = str(value).strip()
        match = re.search(r"/Date\((?P<millis>-?\d+)(?P<offset>[+-]\d{4})?\)/", text)
        try:
            if match:
                instant = datetime.fromtimestamp(int(match.group("millis")) / 1000, tz=timezone.utc)
            else:
                instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if instant.tzinfo is None:
                    instant = instant.replace(tzinfo=timezone.utc)
            timezone_name = str(getattr(settings, "APP_TIMEZONE", "America/Bogota"))
            instant = instant.astimezone(ZoneInfo(timezone_name))
            return instant.strftime("%d/%m/%Y %I:%M %p").replace("AM", "a. m.").replace("PM", "p. m.")
        except (ValueError, OSError, OverflowError):
            return text[:80]

    @classmethod
    def _format_date_long(cls, value: Any) -> Optional[str]:
        formatted = cls._format_date(value)
        if not formatted:
            return None

        match = re.fullmatch(
            r"(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4}) "
            r"(?P<hour>\d{2}):(?P<minute>\d{2}) (?P<period>a\. m\.|p\. m\.)",
            formatted,
        )
        if not match:
            return formatted

        month_index = int(match.group("month")) - 1
        if month_index < 0 or month_index >= len(cls.MONTHS_ES):
            return formatted

        return (
            f"{int(match.group('day'))} de {cls.MONTHS_ES[month_index]} "
            f"de {match.group('year')} a las {int(match.group('hour'))}:"
            f"{match.group('minute')} {match.group('period')}"
        )

    @classmethod
    def _sort_history(cls, rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def key(row: Dict[str, Any]) -> float:
            text = str(row.get("CreationDate") or "")
            match = re.search(r"/Date\((?P<millis>-?\d+)", text)
            if match:
                return float(match.group("millis"))
            try:
                return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                return 0.0
        return sorted(rows, key=key, reverse=True)

    @staticmethod
    def _human_size(value: Any) -> Optional[str]:
        try:
            size = int(value)
        except (TypeError, ValueError):
            return None
        units = ["B", "KB", "MB", "GB"]
        number = float(size)
        for unit in units:
            if number < 1024 or unit == units[-1]:
                return f"{number:.0f} {unit}" if unit == "B" else f"{number:.1f} {unit}"
            number /= 1024
        return None

    @staticmethod
    def _safe_failure(
        reference: TicketReference,
        *,
        status: str,
        audit_action: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = {
            "reference": reference.normalized,
            "status": status,
            **(extra or {}),
        }
        return {
            "handled": True,
            "ok": False,
            "status": status,
            "audit_action": audit_action,
            "message": message,
            "safe_metadata": metadata,
            "ticket_tracking": metadata,
        }


aranda_tracking_service = ArandaTrackingService()