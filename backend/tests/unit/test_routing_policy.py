"""
Pruebas de regresión para routing_policy_service.

Cubre el bug de pérdida de contexto en mensajes cortos de seguimiento
y la correcta clasificación de casos generales vs internos.
"""
import pytest
from app.services.routing_policy_service import RoutingPolicyService


@pytest.fixture
def service():
    return RoutingPolicyService()


# ── Bug: GUIAME no heredaba contexto → pedía URL/aplicativo ──────────────────

class TestFollowUpInheritance:
    """
    Bug: mensajes cortos como "GUIAME", "continúa", "no funcionó" no
    tenían keywords de ofimática, así que clasificaban como
    internal_or_mixed. Eso desactivaba el respaldo de IA general
    y el bot pedía URL o datos de aplicativo sin sentido.
    """

    @pytest.mark.parametrize("msg", [
        "GUIAME",
        "guíame",
        "continúa",
        "sigue",
        "no funcionó",
        "no funciono",
        "y ahora qué hago",
        "dame el paso a paso",
    ])
    def test_follow_up_inherits_general_tech_context(self, service, msg):
        result = service.classify_message(
            msg,
            profile="employee",
            previous_intent_family="general_tech",
        )
        assert result["intent_family"] in {"general_tech", "general_tech_support"}, (
            f"'{msg}' con previous_intent_family='general_tech' debe heredar "
            f"la clasificación general, pero retornó '{result['intent_family']}'"
        )

    def test_follow_up_without_previous_context_is_internal_or_mixed(self, service):
        """Sin contexto previo, un mensaje corto ambiguo va a internal_or_mixed."""
        result = service.classify_message("GUIAME", profile="employee")
        # Sin contexto previo no puede saber que era sobre ofimática
        assert result["intent_family"] == "internal_or_mixed"

    def test_follow_up_does_not_inherit_internal_context(self, service):
        """Un seguimiento de un caso interno NO debe activar el respaldo de IA general."""
        result = service.classify_message(
            "GUIAME",
            profile="support_engineer",
            previous_intent_family="internal_or_mixed",
        )
        # No debe activar general_ai_fallback para casos internos
        assert not result.get("use_general_ai_fallback"), (
            "El respaldo de IA general nunca debe activarse para seguimientos "
            "de casos internos/mixtos — podría inventar datos internos de IQ"
        )


# ── Clasificación correcta de casos generales ─────────────────────────────────

class TestGeneralTechClassification:

    @pytest.mark.parametrize("msg,expected_family", [
        ("no puedo abrir Excel, da error al iniciar", "general_tech"),
        ("cómo hago una tabla dinámica en Excel", "general_tech"),
        ("tengo un problema con la impresora, no imprime", "general_tech"),
        ("no puedo instalar el driver de la impresora", "general_tech"),
        ("Outlook no sincroniza el correo", "general_tech"),
        ("el navegador Chrome guarda cookies de otros usuarios", "general_tech"),
        ("cómo limpio el caché del navegador", "general_tech"),
    ])
    def test_office_tools_classify_as_general_tech(self, service, msg, expected_family):
        result = service.classify_message(msg, profile="employee")
        assert result["intent_family"] == expected_family, (
            f"'{msg}' debe clasificar como '{expected_family}', "
            f"pero retornó '{result['intent_family']}'"
        )
        assert not result["use_rag"], (
            "Preguntas de ofimática general no deben usar RAG interno — "
            "traerían documentos corporativos irrelevantes"
        )

    def test_general_tech_enables_general_ai_fallback(self, service):
        result = service.classify_message(
            "la impresora no imprime", profile="employee"
        )
        assert result.get("use_general_ai_fallback"), (
            "Preguntas de ofimática general deben habilitar el respaldo de IA general"
        )


# ── Casos internos NO deben activar IA general ────────────────────────────────

class TestInternalCasesNoGeneralAI:

    @pytest.mark.parametrize("msg", [
        "el portal AdminREA no carga",
        "el sistema de Aranda no responde",
        "el servidor de producción está caído, ip 10.0.0.5",
        "hay un error en la base de datos de IQ",
        "el procedimiento de ingreso a VPN corporativa falló",
    ])
    def test_internal_cases_do_not_use_general_ai(self, service, msg):
        result = service.classify_message(msg, profile="support_engineer")
        assert not result.get("use_general_ai_fallback"), (
            f"'{msg}' es un caso interno — el respaldo de IA general no debe "
            "activarse porque podría inventar procedimientos o datos internos de IQ"
        )
        assert result["use_rag"], (
            "Casos internos deben usar RAG para buscar en la base de conocimiento"
        )


# ── URL e IP fuerzan señal interna ────────────────────────────────────────────

class TestUrlAndIpForcesInternal:

    def test_url_in_message_forces_internal_signal(self, service):
        result = service.classify_message(
            "https://portal.iq-online.com no carga", profile="employee"
        )
        assert result["internal_signal"]
        assert result["use_rag"]
        assert not result.get("use_general_ai_fallback")

    def test_has_ip_flag_forces_internal_signal(self, service):
        result = service.classify_message(
            "el equipo no conecta", profile="employee", has_ip=True
        )
        assert result["internal_signal"]

    def test_matrix_found_forces_internal(self, service):
        result = service.classify_message(
            "Excel no abre", profile="employee", matrix_found=True
        )
        # matrix_found es señal interna — aunque sea Excel, hay un aplicativo en la matriz
        assert result["internal_signal"]


# ── word-boundary matching (no substring) ─────────────────────────────────────

class TestWordBoundaryMatching:
    """
    El método _find_keyword_hits usa regex con límites de palabra.
    'ip' no debe matchear en 'impresora' o 'equipo'.
    """

    def test_ip_keyword_not_in_impresora(self, service):
        result = service.classify_message(
            "tengo un problema con la impresora de la oficina",
            profile="employee"
        )
        # 'ip' no debe aparecer en internal_hits por estar dentro de 'impresora'
        assert "ip" not in result.get("internal_hits", []), (
            "'ip' aparece como coincidencia interna dentro de 'impresora'. "
            "El matching debe ser por palabra completa, no substring."
        )

    def test_servidor_keyword_matches_when_standalone(self, service):
        result = service.classify_message(
            "el servidor de base de datos no responde",
            profile="support_engineer"
        )
        assert "servidor" in result.get("internal_hits", []) or result["use_rag"]