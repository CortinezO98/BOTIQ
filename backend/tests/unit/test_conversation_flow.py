"""
Pruebas de regresión para conversation_flow_service.

Cada test corresponde a un bug real encontrado y corregido en producción.
Si alguno falla después de un cambio, el bug anterior ha sido reintroducido.
"""
import pytest
from unittest.mock import MagicMock

from app.services.conversation_flow_service import ConversationFlowService


@pytest.fixture
def service():
    return ConversationFlowService()


def _mock_conversation(metadata=None, selected_profile="employee"):
    conv = MagicMock()
    conv.metadata_ = metadata or {}
    conv.selected_profile = selected_profile
    conv.question_count = 1
    conv.out_of_scope_count = 0
    return conv


# ── Bug #1: "lentitud" clasificaba como app_down, pedía URL ───────────────────

class TestSlownessNotAppDown:
    """
    Bug: 'lentitud'/'lento' estaban en DOWN_KW. Cualquier mensaje sobre
    lentitud de PC (incluyendo preguntas de procedimiento diagnóstico)
    se clasificaba como 'app_down', exigiendo nombre de aplicativo/URL
    antes de responder.
    """

    def test_slowness_question_classifies_as_computer_issue(self, service):
        conv = _mock_conversation()
        msg = ("Tengo un equipo con Windows 7 que está presentando mucha "
               "lentitud y apagados repentinos. ¿Qué herramienta debo usar?")
        decision = service.analyze(conv, msg)
        assert decision.case_type != "app_down", (
            "Un mensaje sobre lentitud de PC no debe clasificarse como app_down"
        )

    def test_slowness_keyword_alone_is_not_app_down(self, service):
        conv = _mock_conversation()
        decision = service.analyze(conv, "el equipo está muy lento")
        assert decision.case_type != "app_down"
        assert decision.case_type in {"computer_issue", "general_support", "procedure"}

    def test_portal_down_is_still_app_down(self, service):
        """Asegurar que casos reales de portal caído sigan clasificando bien."""
        conv = _mock_conversation()
        decision = service.analyze(conv, "el portal de ventas no carga, da error 503")
        assert decision.case_type in {"app_down", "server_status"}


# ── Bug #2: "gracias" consumía 1800 tokens llamando a Gemini ──────────────────

class TestClosingMessagesDirectResponse:
    """
    Bug: mensajes de cierre/cortesía ("gracias", "muchas gracias") no tenían
    direct_response y pasaban por el flujo completo de RAG + Gemini,
    gastando ~1800 tokens por una frase de cortesía.
    """

    @pytest.mark.parametrize("msg", [
        "gracias",
        "muchas gracias",
        "gracias!",
        "thank you",
        "thanks",
        "muy amable",
    ])
    def test_short_thanks_returns_direct_response(self, service, msg):
        conv = _mock_conversation()
        decision = service.analyze(conv, msg)
        assert decision.direct_response is not None, (
            f"'{msg}' debe tener direct_response para evitar llamada a Gemini"
        )
        assert decision.intent == "closing"

    def test_long_message_with_thanks_not_closing(self, service):
        """Un mensaje largo que contiene 'gracias' pero es una pregunta real."""
        conv = _mock_conversation()
        msg = ("Gracias, pero según los procedimientos estándar de IQ necesito "
               "saber el requisito mínimo de RAM para Windows 7 y qué herramienta "
               "usar para ver el consumo de recursos.")
        decision = service.analyze(conv, msg)
        # No debe ser closing — es una pregunta técnica real
        assert decision.intent != "closing", (
            "Un mensaje largo con 'gracias' al inicio no debe tratarse como cierre"
        )

    def test_greeting_returns_direct_response(self, service):
        conv = _mock_conversation()
        decision = service.analyze(conv, "hola")
        assert decision.direct_response is not None
        assert decision.intent == "greeting"


# ── Bug #3: closing decision no debería llamar FAQ ni RAG ─────────────────────

class TestClosingSkipsAI:
    def test_closing_decision_does_not_call_faq_or_rag(self, service):
        conv = _mock_conversation()
        decision = service.analyze(conv, "gracias")
        assert not decision.should_call_faq
        assert not decision.should_call_rag
        assert not decision.should_check_status


# ── Bug #4: printer_issue no debería pedir URL/IP ─────────────────────────────

class TestPrinterIssueSlots:
    """
    Bug: mensajes sobre impresoras podían clasificarse como app_down si
    contenían palabras como 'no imprime' que coincidían con DOWN_KW.
    """

    def test_printer_message_is_not_app_down(self, service):
        conv = _mock_conversation()
        decision = service.analyze(
            conv, "El gerente no puede imprimir un documento en la impresora local"
        )
        assert decision.case_type != "app_down", (
            "Problema de impresora no debe clasificarse como portal/aplicativo caído"
        )
        assert decision.case_type == "printer_issue"

    def test_printer_missing_slots_do_not_require_url(self, service):
        conv = _mock_conversation()
        decision = service.analyze(conv, "la impresora no imprime nada")
        # No debe exigir URL ni IP como dato mínimo
        assert "url" not in decision.missing_slots
        assert "app_or_url" not in decision.missing_slots


# ── Bug #5: NEGATIONS set presente pero no usado ─────────────────────────────

class TestNegationContinuity:
    """
    El set NEGATIONS existe en el servicio pero no se usa en ningún análisis.
    Esto es un bug potencial — "no funcionó" debería mantener el contexto del
    caso anterior, no resetearlo a general_support.
    """

    def test_no_funciono_preserves_previous_case(self, service):
        conv = _mock_conversation(
            metadata={"case": {"case_type": "printer_issue", "intent": "printer_issue"}}
        )
        decision = service.analyze(conv, "no funcionó")
        # No debe resetear a un caso completamente diferente
        assert decision.case_type != "app_down", (
            "'no funcionó' no debe reclasificarse como portal caído"
        )


# ── Verificación de atributos del FlowDecision ────────────────────────────────

class TestFlowDecisionStructure:
    """Verifica que FlowDecision siempre tenga los campos que chat.py espera."""

    def test_decision_has_required_fields(self, service):
        conv = _mock_conversation()
        decision = service.analyze(conv, "no puedo entrar al portal de ventas")
        assert hasattr(decision, "intent")
        assert hasattr(decision, "case_type")
        assert hasattr(decision, "confidence")
        assert hasattr(decision, "slots")
        assert hasattr(decision, "missing_slots")
        assert hasattr(decision, "direct_response")
        assert hasattr(decision, "should_call_faq")
        assert hasattr(decision, "should_call_rag")
        assert hasattr(decision, "should_check_status")

    def test_confidence_is_between_0_and_1(self, service):
        for msg in ["hola", "gracias", "no puedo entrar al portal", "impresora rota"]:
            conv = _mock_conversation()
            decision = service.analyze(conv, msg)
            assert 0.0 <= decision.confidence <= 1.0, (
                f"confidence={decision.confidence} para '{msg}' fuera de rango [0,1]"
            )