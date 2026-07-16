from types import SimpleNamespace

from app.services.conversation_flow_service import ConversationFlowService, FlowDecision


def _conversation(**overrides):
    data = {
        "escalated_to_aranda": False,
        "aranda_ticket_id": None,
        "resolution_attempts": 0,
        "ticket_eligible": False,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _decision():
    return FlowDecision(
        intent="application_down_or_error",
        case_type="app_down",
        confidence=0.95,
        slots={
            "app_or_url": "https://portal.interno.local",
            "error_or_symptom": "Error 503",
            "error_code": "503",
            "affected_scope": "varios usuarios",
        },
        severity="critical",
    )


def test_http_503_does_not_bypass_last_resort_policy(monkeypatch):
    service = ConversationFlowService()
    monkeypatch.setattr(
        "app.services.conversation_flow_service.settings.MIN_RESOLUTION_ATTEMPTS_BEFORE_TICKET",
        2,
    )

    allowed, reason = service.can_escalate_to_aranda(
        _conversation(resolution_attempts=0, ticket_eligible=False),
        _decision(),
        explicit_request=True,
    )

    assert allowed is False
    assert "2 validaciones" in reason


def test_ticket_is_offered_only_after_case_is_marked_unresolved(monkeypatch):
    service = ConversationFlowService()
    monkeypatch.setattr(
        "app.services.conversation_flow_service.settings.MIN_RESOLUTION_ATTEMPTS_BEFORE_TICKET",
        2,
    )

    assert service.should_offer_ticket(
        _conversation(resolution_attempts=2, ticket_eligible=False),
        _decision(),
        {"status": "down"},
    ) is False

    assert service.should_offer_ticket(
        _conversation(resolution_attempts=2, ticket_eligible=True),
        _decision(),
        {"status": "down"},
    ) is True
