from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import re

from app.core.config import settings
from app.models.conversation import Conversation


@dataclass
class FlowDecision:
    """
    Resultado del análisis conversacional.

    Este objeto NO responde con IA. Solo decide:
    - qué tipo de caso es,
    - qué datos mínimos faltan,
    - si se puede consultar FAQ/RAG/API de estados,
    - si el caso puede preparar ticket de Aranda.
    """
    intent: str
    case_type: str
    confidence: float = 0.0
    slots: Dict[str, Any] = field(default_factory=dict)
    missing_slots: List[str] = field(default_factory=list)
    next_question: Optional[str] = None
    should_call_faq: bool = True
    should_call_rag: bool = True
    should_check_status: bool = False
    should_analyze_server: bool = False
    should_register_gap: bool = False
    should_offer_ticket: bool = False
    direct_response: Optional[str] = None
    severity: str = "medium"


class ConversationFlowService:
    """
    Capa de flujo conversacional para BOTIQ.

    Objetivo:
    - Evitar que BOTIQ responda de forma plana.
    - Guiar al usuario por diagnóstico.
    - Pedir datos mínimos antes de consultar o escalar.
    - Usar Aranda solo como última instancia.
    """

    ERROR_CODE_REGEX = re.compile(r"\b(?:error\s*)?(4\d{2}|5\d{2})\b", re.IGNORECASE)
    URL_REGEX = re.compile(r"(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)")
    IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

    GREETINGS = {"hola", "buenas", "buenos dias", "buenos días", "buenas tardes", "buenas noches", "ayuda", "soporte"}
    # Mensajes de cierre/cortesía: no necesitan FAQ/RAG/Gemini, pero antes
    # pasaban por el flujo completo igual que una pregunta técnica real
    # (~1800 tokens y ~10s solo para responder "de nada"). Se detectan por
    # contener una de estas palabras Y ser mensajes cortos, para no atrapar
    # por accidente un mensaje largo que solo menciona "gracias" de pasada.
    THANKS_KW = ["gracias", "thank you", "thanks", "muy amable"]
    THANKS_MAX_CHARS = 60
    CONFIRMATIONS = {"si", "sí", "claro", "correcto", "confirmo", "dale", "ok", "de acuerdo", "continua", "continúa"}
    NEGATIONS = {"no", "negativo", "aun no", "aún no", "todavia no", "todavía no", "no funciono", "no funcionó", "sigue igual"}

    ACCESS_KW = [
        "no puedo entrar", "no me deja entrar", "no me deja ingresar", "no ingreso",
        "bloqueo", "bloqueado", "login", "iniciar sesión", "iniciar sesion",
        "usuario bloqueado", "contraseña", "password", "credenciales", "portal"
    ]
    # "lento"/"lentitud" se sacaron de aquí: por sí solos no implican que un
    # aplicativo/portal esté caído, también describen un equipo lento (ver
    # COMPUTER_KW). Como esta lista se evalúa PRIMERO en _detect_intent,
    # tenerlos aquí hacía que CUALQUIER mensaje sobre lentitud del equipo
    # (incluyendo preguntas de procedimiento sobre diagnóstico de SO) se
    # clasificara como "app_down", exigiendo nombre de aplicativo/URL y
    # alcance antes de responder, en vez de contestar la pregunta directamente.
    DOWN_KW = [
        "caído", "caido", "no abre", "no carga", "no responde",
        "error 500", "error 501", "error 502", "error 503", "error 504", "gateway", "timeout"
    ]
    PRINTER_KW = ["impresora", "impresión", "impresion", "imprimir", "cola de impresión", "cola de impresion"]
    COMPUTER_KW = ["computador", "pc", "equipo", "pantalla azul", "windows", "lento", "lentitud", "se reinicia", "teclado", "mouse"]
    FILE_KW = ["archivo", "excel", "word", "pdf", "dañado", "danado", "no abre el archivo", "no guarda", "macro"]
    PROCEDURE_KW = ["procedimiento", "manual", "paso a paso", "cómo", "como", "guía", "guia", "instructivo"]
    SERVER_KW = ["servidor", "server", "cpu", "memoria", "ram", "disco", "ping", "infraestructura", "servicio"]

    # Datos mínimos por tipo de caso.
    REQUIRED_SLOTS = {
        "access_issue": ["app_or_url", "error_or_symptom"],
        "app_down": ["app_or_url", "error_or_symptom", "affected_scope"],
        "printer_issue": ["device_or_service", "error_or_symptom"],
        "computer_issue": ["device_or_service", "error_or_symptom"],
        "file_issue": ["device_or_service", "error_or_symptom"],
        "procedure": ["topic"],
        "server_status": ["app_or_url"],
        "general_support": ["error_or_symptom"],
    }

    SLOT_LABELS = {
        "app_or_url": "nombre del aplicativo, portal, URL o IP",
        "error_or_symptom": "mensaje de error o síntoma exacto",
        "affected_scope": "si le ocurre solo a un usuario o a varios",
        "device_or_service": "equipo, impresora, archivo o servicio afectado",
        "topic": "tema o procedimiento exacto",
        "evidence": "captura o evidencia del error",
    }

    def analyze(
        self,
        conversation: Conversation,
        message: str,
        image_analysis: Optional[str] = None,
    ) -> FlowDecision:
        msg = (message or "").strip()
        lower = msg.lower()
        previous_case = self.get_case_state(conversation)

        if lower in self.GREETINGS:
            return self._welcome_decision(conversation.selected_profile or "employee")

        if len(msg) <= self.THANKS_MAX_CHARS and any(k in lower for k in self.THANKS_KW):
            return self._closing_decision(conversation.selected_profile or "employee")

        if lower in self.CONFIRMATIONS and previous_case.get("pending_ticket_confirmation"):
            return FlowDecision(
                intent="ticket_confirmation",
                case_type=previous_case.get("case_type", "general_support"),
                confidence=0.95,
                slots=previous_case.get("slots", {}),
                should_call_faq=False,
                should_call_rag=False,
                should_check_status=False,
                direct_response=None,
                severity=previous_case.get("severity", "medium"),
            )

        intent, case_type, confidence = self._detect_intent(lower)
        slots = self._extract_slots(msg, lower, image_analysis=image_analysis)

        # Hereda slots previos de la conversación y completa con lo nuevo.
        merged_slots = dict(previous_case.get("slots") or {})
        for key, value in slots.items():
            if value not in (None, "", [], {}):
                merged_slots[key] = value

        # Si cambia claramente el tipo de caso, conserva datos útiles pero actualiza clasificación.
        if not case_type and previous_case.get("case_type"):
            case_type = previous_case["case_type"]
        if not intent and previous_case.get("intent"):
            intent = previous_case["intent"]

        case_type = case_type or "general_support"
        intent = intent or "general_support"

        required = self.REQUIRED_SLOTS.get(case_type, self.REQUIRED_SLOTS["general_support"])
        missing = [slot for slot in required if not self._slot_has_value(merged_slots, slot)]

        has_url_or_ip = bool(merged_slots.get("url") or merged_slots.get("ip") or merged_slots.get("app_or_url"))
        error_code = str(merged_slots.get("error_code") or "")
        critical_error = error_code in {"500", "501", "502", "503", "504"}

        should_check_status = has_url_or_ip and case_type in {"access_issue", "app_down", "server_status", "general_support"}
        should_analyze_server = case_type == "server_status" or critical_error

        severity = "critical" if critical_error or case_type == "app_down" else "medium"

        decision = FlowDecision(
            intent=intent,
            case_type=case_type,
            confidence=confidence,
            slots=merged_slots,
            missing_slots=missing,
            should_call_faq=True,
            should_call_rag=True,
            should_check_status=should_check_status,
            should_analyze_server=should_analyze_server,
            should_register_gap=False,
            should_offer_ticket=False,
            severity=severity,
        )

        if missing and self._should_collect_minimum_data_first(case_type, conversation.selected_profile):
            decision.next_question = self._build_next_question(case_type, missing, merged_slots)
            decision.direct_response = decision.next_question
            decision.should_call_faq = False if case_type in {"access_issue", "app_down"} else True
            decision.should_call_rag = False if case_type in {"access_issue", "app_down"} else True
            decision.should_check_status = False

        return decision

    def get_case_state(self, conversation: Conversation) -> Dict[str, Any]:
        meta = conversation.metadata_ or {}
        return dict(meta.get("case") or {})

    def merge_case_metadata(
        self,
        metadata: Optional[Dict[str, Any]],
        decision: FlowDecision,
        pending_ticket_confirmation: Optional[bool] = None,
    ) -> Dict[str, Any]:
        meta = dict(metadata or {})
        case = dict(meta.get("case") or {})
        case.update(
            {
                "intent": decision.intent,
                "case_type": decision.case_type,
                "confidence": decision.confidence,
                "slots": decision.slots,
                "missing_slots": decision.missing_slots,
                "severity": decision.severity,
            }
        )
        if pending_ticket_confirmation is not None:
            case["pending_ticket_confirmation"] = pending_ticket_confirmation
        meta["case"] = case
        return meta

    def can_escalate_to_aranda(
        self,
        conversation: Conversation,
        decision: FlowDecision,
        explicit_request: bool = False,
    ) -> tuple[bool, str]:
        """
        Regla estricta de última instancia para no llenar Aranda:
        - Debe existir confirmación explícita del usuario.
        - Deben existir los datos mínimos del caso.
        - BOTIQ debe haber agotado los intentos mínimos de solución.
        - La conversación debe estar marcada como no resuelta/elegible.
        - No existe bypass automático para errores 5xx.
        """
        if conversation.escalated_to_aranda or conversation.aranda_ticket_id:
            return False, (
                "Ya existe un ticket asociado a esta conversación: "
                f"{conversation.aranda_ticket_id or 'registrado'}"
            )

        if not explicit_request:
            return False, "Para crear el ticket necesito tu confirmación explícita."

        slots = decision.slots or {}
        has_target = bool(
            slots.get("app_or_url")
            or slots.get("url")
            or slots.get("ip")
            or slots.get("device_or_service")
            or slots.get("topic")
        )
        has_problem = bool(
            slots.get("error_or_symptom")
            or slots.get("error_code")
            or slots.get("evidence")
        )
        has_scope = bool(slots.get("affected_scope")) or decision.case_type not in {
            "app_down",
            "access_issue",
        }

        missing = []
        if not has_target:
            missing.append("aplicativo, URL, IP, equipo o servicio afectado")
        if not has_problem:
            missing.append("error o síntoma exacto")
        if not has_scope:
            missing.append("alcance del problema: solo tú o varios usuarios")

        if missing:
            return (
                False,
                "Antes de crear el ticket necesito completar estos datos para no generar "
                "solicitudes incompletas en Aranda:\n"
                + "\n".join(f"- {item}" for item in missing),
            )

        attempts = int(conversation.resolution_attempts or 0)
        min_attempts = max(1, int(settings.MIN_RESOLUTION_ATTEMPTS_BEFORE_TICKET))
        if attempts < min_attempts:
            return (
                False,
                f"Antes de crear un ticket debemos agotar al menos {min_attempts} validaciones. "
                "Primero revisaré FAQ/base de conocimiento, estado del aplicativo o servidor "
                "y los pasos básicos de solución.",
            )

        if not bool(conversation.ticket_eligible):
            return (
                False,
                "La conversación todavía no ha sido marcada como no resuelta. "
                "El ticket solo se crea como última instancia.",
            )

        return True, "Validaciones agotadas, caso no resuelto y confirmación recibida."

    def should_offer_ticket(
        self,
        conversation: Conversation,
        decision: FlowDecision,
        app_status: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Solo ofrece Aranda cuando el flujo de solución ya fue agotado.

        Un estado crítico o un HTTP 5xx aumenta la severidad del caso, pero no
        adelanta el ticket ni evita las validaciones mínimas.
        """
        slots = decision.slots or {}
        has_target = bool(
            slots.get("app_or_url")
            or slots.get("url")
            or slots.get("ip")
            or slots.get("device_or_service")
            or slots.get("topic")
        )
        attempts = int(conversation.resolution_attempts or 0)
        min_attempts = max(1, int(settings.MIN_RESOLUTION_ATTEMPTS_BEFORE_TICKET))
        return bool(
            conversation.ticket_eligible
            and attempts >= min_attempts
            and has_target
            and not conversation.escalated_to_aranda
            and not conversation.aranda_ticket_id
        )

    def build_ticket_offer_message(self, decision: FlowDecision) -> str:
        slots = decision.slots or {}
        lines = [
            "Con la información validada, este caso puede requerir escalamiento a Aranda como última instancia.",
            "",
            "Resumen que se enviaría al ticket:",
            f"- Caso: {decision.case_type}",
            f"- Aplicativo/URL/IP: {slots.get('app_or_url') or slots.get('url') or slots.get('ip') or 'No registrado'}",
            f"- Error/síntoma: {slots.get('error_or_symptom') or slots.get('error_code') or 'No registrado'}",
            f"- Alcance: {slots.get('affected_scope') or 'No registrado'}",
            f"- Evidencia: {'Sí' if slots.get('evidence') else 'No registrada'}",
            "",
            "¿Confirmas que deseas crear el ticket en Aranda?",
        ]
        return "\n".join(lines)

    def _welcome_decision(self, profile: str) -> FlowDecision:
        if profile == "support_engineer":
            text = (
                "Hola, soy BOTIQ, tu asistente virtual de soporte corporativo.\n\n"
                "Como Ingeniero de Soporte puedo ayudarte a:\n"
                "1. Consultar preguntas frecuentes y respuestas aprobadas.\n"
                "2. Buscar procedimientos en la base de conocimiento.\n"
                "3. Revisar información de aplicativos, URLs, IPs y servidores asociados.\n"
                "4. Analizar capturas de error.\n"
                "5. Preparar un ticket de Aranda solo cuando ya existan validaciones suficientes.\n\n"
                "Cuéntame qué está pasando o qué procedimiento necesitas revisar."
            )
        else:
            text = (
                "Hola, soy BOTIQ. Estamos aquí para asistirte.\n\n"
                "Puedo ayudarte con dudas o problemas como:\n"
                "1. Bloqueos de portales o accesos.\n"
                "2. Errores del computador, Word, Excel, Outlook, Teams o VPN.\n"
                "3. Problemas con impresoras o archivos.\n"
                "4. Validación de URLs, aplicativos o servicios internos.\n"
                "5. Escalamiento a Aranda solo como última instancia y con la información completa.\n\n"
                "Cuéntame qué problema tienes y te guiaré paso a paso."
            )
        return FlowDecision(
            intent="greeting",
            case_type="welcome",
            confidence=1.0,
            direct_response=text,
            should_call_faq=False,
            should_call_rag=False,
            should_check_status=False,
        )

    def _closing_decision(self, profile: str) -> FlowDecision:
        if profile == "support_engineer":
            text = "Con gusto. Si surge otro caso o necesitas validar algo más, aquí estoy."
        else:
            text = "¡Con gusto! Si tienes otra duda o problema, aquí estoy para ayudarte."
        return FlowDecision(
            intent="closing",
            case_type="closing",
            confidence=1.0,
            direct_response=text,
            should_call_faq=False,
            should_call_rag=False,
            should_check_status=False,
        )

    def _detect_intent(self, lower: str) -> tuple[str, str, float]:
        if any(k in lower for k in self.DOWN_KW):
            return "application_down_or_error", "app_down", 0.9
        if any(k in lower for k in self.ACCESS_KW):
            return "access_issue", "access_issue", 0.85
        if any(k in lower for k in self.PRINTER_KW):
            return "printer_issue", "printer_issue", 0.85
        if any(k in lower for k in self.FILE_KW):
            return "file_issue", "file_issue", 0.8
        if any(k in lower for k in self.COMPUTER_KW):
            return "computer_issue", "computer_issue", 0.75
        if any(k in lower for k in self.SERVER_KW):
            return "server_status", "server_status", 0.8
        if any(k in lower for k in self.PROCEDURE_KW):
            return "procedure_lookup", "procedure", 0.78
        return "general_support", "general_support", 0.55

    def _extract_slots(self, msg: str, lower: str, image_analysis: Optional[str] = None) -> Dict[str, Any]:
        slots: Dict[str, Any] = {}

        url = self.URL_REGEX.search(msg)
        if url:
            slots["url"] = url.group(0).rstrip(".,;")
            slots["app_or_url"] = slots["url"]

        ip = self.IP_REGEX.search(msg)
        if ip:
            slots["ip"] = ip.group(0)
            slots.setdefault("app_or_url", slots["ip"])

        code = self.ERROR_CODE_REGEX.search(msg)
        if code:
            slots["error_code"] = code.group(1)
            slots["error_or_symptom"] = f"Error {code.group(1)}"

        if image_analysis:
            slots["evidence"] = True
            slots["image_analysis"] = image_analysis
            slots.setdefault("error_or_symptom", self._shorten(image_analysis, 240))

        if any(k in lower for k in ["varios", "todos", "masivo", "masiva", "área", "area", "sede"]):
            slots["affected_scope"] = "varios usuarios"
        elif any(k in lower for k in ["solo yo", "solamente yo", "a mi", "a mí", "mi usuario"]):
            slots["affected_scope"] = "un usuario"

        # Aplicativo/portal mencionado sin URL.
        app_match = re.search(r"(?:portal|aplicativo|app|sistema|url|link)\s+(?:de\s+)?([a-zA-Z0-9_\- .]{2,60})", msg, re.IGNORECASE)
        if app_match and not slots.get("app_or_url"):
            slots["app_or_url"] = app_match.group(1).strip(" .,:;")

        if any(k in lower for k in self.PRINTER_KW):
            slots["device_or_service"] = "impresora"
        elif any(k in lower for k in self.FILE_KW):
            slots["device_or_service"] = "archivo/ofimática"
        elif any(k in lower for k in self.COMPUTER_KW):
            slots["device_or_service"] = "computador"

        if not slots.get("error_or_symptom") and len(msg) >= 12:
            slots["error_or_symptom"] = self._shorten(msg, 220)

        if any(k in lower for k in self.PROCEDURE_KW):
            slots["topic"] = self._shorten(msg, 160)

        return slots

    def _should_collect_minimum_data_first(self, case_type: str, profile: Optional[str]) -> bool:
        # Para procedimientos técnicos se puede consultar la base de conocimiento de una vez.
        if case_type == "procedure":
            return False
        # Para soporte y empleado, los incidentes operativos sí deben guiarse por slots.
        return case_type in {"access_issue", "app_down", "printer_issue", "computer_issue", "file_issue", "server_status"}

    def _build_next_question(self, case_type: str, missing: List[str], slots: Dict[str, Any]) -> str:
        readable = [self.SLOT_LABELS.get(m, m) for m in missing]
        intro = {
            "access_issue": "Entiendo que tienes un problema de acceso.",
            "app_down": "Entiendo que el aplicativo, portal o URL presenta un error o no responde.",
            "printer_issue": "Entiendo que tienes un problema con impresora.",
            "computer_issue": "Entiendo que tienes un problema con tu equipo.",
            "file_issue": "Entiendo que tienes un problema con un archivo o herramienta ofimática.",
            "server_status": "Entiendo que quieres validar un servicio, aplicativo o servidor.",
        }.get(case_type, "Para ayudarte bien necesito completar algunos datos.")

        question = intro + "\n\nPara continuar necesito:\n" + "\n".join(f"- {x}" for x in readable)
        question += "\n\nPuedes responder en un solo mensaje. Si tienes captura del error, también puedes adjuntarla."
        return question

    @staticmethod
    def _slot_has_value(slots: Dict[str, Any], slot: str) -> bool:
        value = slots.get(slot)
        return value not in (None, "", [], {})

    @staticmethod
    def _shorten(text: str, max_len: int) -> str:
        text = " ".join((text or "").split())
        return text[:max_len].strip()


conversation_flow_service = ConversationFlowService()