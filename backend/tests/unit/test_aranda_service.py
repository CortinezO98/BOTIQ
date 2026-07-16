from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import settings
from app.services.aranda_service import ArandaService, ArandaSession


def _conversation(**overrides):
    values = {
        "id": "11111111-2222-3333-4444-555555555555",
        "session_id": "session-botiq",
        "selected_profile": "employee",
        "question_count": 4,
        "resolution_attempts": 2,
        "ticket_eligible": True,
        "detected_url": "https://portal.interno.local",
        "detected_ip": None,
        "application_status_snapshot": {"status": "down"},
        "escalated_to_aranda": False,
        "aranda_ticket_id": None,
        "aranda_ticket_status": None,
        "aranda_ticket_created_at": None,
        "metadata_": {
            "case": {
                "intent": "ticket_confirmation",
                "slots": {
                    "app_or_url": "https://portal.interno.local",
                    "error_or_symptom": "Error 503",
                    "affected_scope": "varios usuarios",
                },
            }
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _user():
    return SimpleNamespace(
        id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        full_name="Usuario Prueba",
        email="usuario@iq-online.com",
    )


def _configure(monkeypatch):
    values = {
        "ARANDA_ENABLED": True,
        "ARANDA_API_URL": "https://aranda.example/ASDKAPI",
        "ARANDA_ALLOWED_HOSTS": "aranda.example",
        "ARANDA_USERNAME": "cuenta.tecnica",
        "ARANDA_PASSWORD": "secret",
        "ARANDA_DEFAULT_ITEM_TYPE": 1,
        "ARANDA_PROJECT_ID": 2,
        "ARANDA_CATEGORY_ID": 2499,
        "ARANDA_GROUP_ID": 33,
        "ARANDA_SERVICE_ID": 2418,
        "ARANDA_SLA_ID": 2454,
        "ARANDA_REGISTRY_TYPE_ID": 6,
        "ARANDA_URGENCY_ID": 3,
        "ARANDA_AUTHOR_ID": 0,
        "ARANDA_CUSTOMER_ID": 0,
        "ARANDA_COMPANY_ID": 0,
        "ARANDA_RESPONSIBLE_ID": 0,
        "ARANDA_CI_ID": 0,
        "ARANDA_VERIFY_TLS": True,
        "ARANDA_CA_BUNDLE": "",
        "ARANDA_TIMEOUT_SECONDS": 15,
        "ARANDA_CONNECT_TIMEOUT_SECONDS": 5,
        "ARANDA_CLOSE_SESSION_AFTER_REQUEST": True,
        "ARANDA_MAX_SUBJECT_CHARS": 180,
        "ARANDA_MAX_DESCRIPTION_CHARS": 12000,
        "MIN_RESOLUTION_ATTEMPTS_BEFORE_TICKET": 2,
    }
    for name, value in values.items():
        monkeypatch.setattr(settings, name, value, raising=False)


def test_parse_field_value_response():
    service = ArandaService()
    parsed = service._field_values_to_dict(
        [
            {"Field": "itemId", "Value": "4158"},
            {"Field": "composedItemId", "Value": "IM-55175-2-19537"},
            {"Field": "result", "Value": "True"},
        ]
    )
    assert parsed["itemid"] == "4158"
    assert parsed["composeditemid"] == "IM-55175-2-19537"
    assert service._as_bool(parsed["result"]) is True


def test_policy_blocks_ticket_before_last_resort(monkeypatch):
    _configure(monkeypatch)
    service = ArandaService()
    conversation = _conversation(resolution_attempts=1, ticket_eligible=False)

    result = service.validate_last_resort_policy(
        conversation,
        explicit_confirmation=True,
        subject="Portal no responde",
        description="El portal devuelve error 503 para varios usuarios.",
    )

    assert result.allowed is False
    assert result.code == "resolution_attempts_pending"


def test_policy_requires_explicit_confirmation(monkeypatch):
    _configure(monkeypatch)
    service = ArandaService()
    conversation = _conversation(metadata_={"case": {"intent": "general_support", "slots": {}}})

    result = service.validate_last_resort_policy(
        conversation,
        explicit_confirmation=None,
        subject="Portal no responde",
        description="El portal devuelve error 503 para varios usuarios.",
    )

    assert result.allowed is False
    assert result.code == "explicit_confirmation_required"


@pytest.mark.asyncio
async def test_create_ticket_uses_asdk_contract_and_verifies(monkeypatch):
    _configure(monkeypatch)
    service = ArandaService()
    seen = {"create_body": None, "authorization": None}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/item/add/1"):
            seen["authorization"] = request.headers.get("Authorization")
            seen["create_body"] = request.read().decode("utf-8")
            return httpx.Response(
                200,
                json=[
                    {"Field": "itemId", "Value": "4158"},
                    {"Field": "composedItemId", "Value": "IM-55175-2-19537"},
                    {"Field": "isClosed", "Value": "False"},
                    {"Field": "result", "Value": "True"},
                ],
            )
        if request.method == "GET" and "/item/4158/1/3913" in request.url.path:
            return httpx.Response(
                200,
                json={
                    "Id": 4158,
                    "ComposedId": "IM-55175-2-19537",
                    "StateId": 1,
                    "StateName": "Registrado",
                    "IsClosed": False,
                    "ProjectId": 2,
                },
            )
        raise AssertionError(f"Petición inesperada: {request.method} {request.url}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    @asynccontextmanager
    async def fake_session():
        async with client:
            yield client, ArandaSession(user_id=3913, session_id="SESSION-ASDK")

    monkeypatch.setattr(service, "_authenticated_session", fake_session)

    result = await service.create_ticket(
        _conversation(),
        _user(),
        "Portal no responde",
        "Después de las validaciones realizadas, el portal continúa con error 503.",
        explicit_confirmation=True,
    )

    assert result["created"] is True
    assert result["ticket_id"] == "IM-55175-2-19537"
    assert result["verification"]["verified"] is True
    assert seen["authorization"] == "SESSION-ASDK"
    assert "Bearer" not in seen["authorization"]
    assert '"Field":"ProjectId"' in seen["create_body"].replace(" ", "")
    assert "Referencia: BOTIQ-" in seen["create_body"]


@pytest.mark.asyncio
async def test_timeout_is_not_retried_and_requires_reconciliation(monkeypatch):
    _configure(monkeypatch)
    service = ArandaService()
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        if request.method == "POST" and request.url.path.endswith("/item/add/1"):
            calls += 1
            raise httpx.ReadTimeout("timeout", request=request)
        raise AssertionError(f"Petición inesperada: {request.method} {request.url}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    @asynccontextmanager
    async def fake_session():
        async with client:
            yield client, ArandaSession(user_id=3913, session_id="SESSION-ASDK")

    monkeypatch.setattr(service, "_authenticated_session", fake_session)

    result = await service.create_ticket(
        _conversation(),
        _user(),
        "Portal no responde",
        "Después de las validaciones realizadas, el portal continúa con error 503.",
        explicit_confirmation=True,
    )

    assert calls == 1
    assert result["created"] is False
    assert result["status"] == "creation_unknown"
    assert result["requires_reconciliation"] is True


def test_mark_ticket_result_only_sets_created_at_on_success():
    service = ArandaService()
    conversation = _conversation(ticket_eligible=True)

    service.mark_ticket_result(
        conversation,
        {
            "created": False,
            "status": "creation_unknown",
            "correlation_id": "BOTIQ-TEST",
            "error_code": "ArandaTimeout",
            "requires_reconciliation": True,
        },
    )

    assert conversation.aranda_ticket_created_at is None
    assert conversation.escalated_to_aranda is False
    assert conversation.metadata_["aranda"]["requires_reconciliation"] is True
