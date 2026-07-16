import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.aranda_service import ArandaService, _from_field_value, _to_field_value


def _fv_response(status_code: int, fields: dict) -> httpx.Response:
    body = [{"Field": k, "Value": v} for k, v in fields.items()]
    return httpx.Response(status_code=status_code, content=json.dumps(body).encode())


def _raw_response(status_code: int, text: str) -> httpx.Response:
    return httpx.Response(status_code=status_code, content=text.encode())


def _configure_settings(monkeypatch):
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_BASE_URL", "https://aranda.test.com/ASDKAPI")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_API_VERSION", "v8.6")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_USERNAME", "botiq_svc")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_PASSWORD", "secret123")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_AUTHOR_ID", "3913")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_GROUP_ID", "33")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_SLA_ID", "2454")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_PROJECT_ID", "2")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_CATEGORY_ID", "2499")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_SERVICE_ID", "2418")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_REGISTRY_TYPE_ID", "6")
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_ITEM_TYPE", 1)
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_TIMEOUT_SECONDS", 5)


class FakeConversation:
    id = "11111111-1111-1111-1111-111111111111"
    selected_profile = "employee"
    session_id = "sess-1"
    question_count = 2
    resolution_attempts = 1
    detected_url = None
    detected_ip = None
    application_status_snapshot = None
    aranda_ticket_id = None
    aranda_ticket_status = None
    aranda_ticket_created_at = None
    escalated_to_aranda = False


class FakeUser:
    email = "empleado@iq-online.com"
    full_name = "Empleado de Prueba"
    id = "22222222-2222-2222-2222-222222222222"


def test_field_value_roundtrip():
    original = {"AuthorId": 3913, "Description": "algo", "Skip": None}
    fv = _to_field_value(original)
    # None se omite -- Aranda no espera "Value": null para campos no provistos.
    assert {"Field": "Skip", "Value": None} not in fv
    assert {"Field": "AuthorId", "Value": 3913} in fv

    parsed = _from_field_value(fv)
    assert parsed == {"AuthorId": 3913, "Description": "algo"}


def test_is_configured_false_when_missing_fields(monkeypatch):
    _configure_settings(monkeypatch)
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_SLA_ID", "")
    service = ArandaService()
    assert service.is_configured() is False
    assert "ARANDA_SLA_ID" in service.get_missing_config()


@pytest.mark.asyncio
async def test_create_ticket_logs_in_and_creates_case(monkeypatch):
    _configure_settings(monkeypatch)
    service = ArandaService()

    login_response = _fv_response(200, {"userId": "471", "sessionId": "TOKEN-ABC", "result": "True"})
    create_response = _fv_response(
        200,
        {"itemId": "4158", "composedItemId": "IM-55175-2-19537", "isClosed": "False", "result": "True"},
    )

    mock_request = AsyncMock(side_effect=[create_response])
    mock_post = AsyncMock(side_effect=[login_response])

    with patch("httpx.AsyncClient.post", mock_post), patch("httpx.AsyncClient.request", mock_request):
        result = await service.create_ticket(
            conversation=FakeConversation(),
            current_user=FakeUser(),
            subject="Portal caído",
            description="El usuario reporta que el portal no carga.",
        )

    assert result["created"] is True
    assert result["ticket_id"] == "IM-55175-2-19537"
    assert result["item_id"] == "4158"

    # Confirma que sí se logueó antes de crear el caso.
    mock_post.assert_awaited_once()
    login_call_url = mock_post.await_args.args[0]
    assert login_call_url == "https://aranda.test.com/ASDKAPI/api/v8.6/user/login"

    # Confirma el cuerpo real enviado a /item/add/{itemType} -- formato field-value real.
    create_call = mock_request.await_args
    assert create_call.args[0] == "POST"
    assert create_call.args[1] == "https://aranda.test.com/ASDKAPI/api/v8.6/item/add/1"
    sent_body = create_call.kwargs["json"]
    sent_fields = _from_field_value(sent_body)
    assert sent_fields["AuthorId"] == 3913
    assert sent_fields["GroupId"] == 33
    assert sent_fields["SlaId"] == 2454
    assert sent_fields["Description"] == "El usuario reporta que el portal no carga."
    # Header de sesión: token crudo, SIN prefijo "Bearer" (así lo espera ASDK).
    assert create_call.kwargs["headers"]["Authorization"] == "TOKEN-ABC"


@pytest.mark.asyncio
async def test_create_ticket_reuses_cached_session_across_calls(monkeypatch):
    _configure_settings(monkeypatch)
    service = ArandaService()

    login_response = _fv_response(200, {"userId": "471", "sessionId": "TOKEN-ABC", "result": "True"})
    create_response = _fv_response(
        200, {"itemId": "1", "composedItemId": "IM-1", "isClosed": "False", "result": "True"}
    )

    mock_post = AsyncMock(side_effect=[login_response])
    mock_request = AsyncMock(side_effect=[create_response, create_response])

    with patch("httpx.AsyncClient.post", mock_post), patch("httpx.AsyncClient.request", mock_request):
        await service.create_ticket(FakeConversation(), FakeUser(), "Caso 1", "Desc 1")
        await service.create_ticket(FakeConversation(), FakeUser(), "Caso 2", "Desc 2")

    # Solo un login para dos casos creados -- la sesión se reutiliza.
    mock_post.assert_awaited_once()
    assert mock_request.await_count == 2


@pytest.mark.asyncio
async def test_create_ticket_relogins_once_when_session_expires(monkeypatch):
    _configure_settings(monkeypatch)
    service = ArandaService()

    first_login = _fv_response(200, {"userId": "471", "sessionId": "TOKEN-OLD", "result": "True"})
    second_login = _fv_response(200, {"userId": "471", "sessionId": "TOKEN-NEW", "result": "True"})
    expired_response = _raw_response(400, "InvalidSessionId")
    success_response = _fv_response(
        200, {"itemId": "1", "composedItemId": "IM-1", "isClosed": "False", "result": "True"}
    )

    mock_post = AsyncMock(side_effect=[first_login, second_login])
    mock_request = AsyncMock(side_effect=[expired_response, success_response])

    with patch("httpx.AsyncClient.post", mock_post), patch("httpx.AsyncClient.request", mock_request):
        result = await service.create_ticket(FakeConversation(), FakeUser(), "Caso", "Desc")

    assert result["created"] is True
    # Un login inicial + un re-login automático tras la sesión vencida.
    assert mock_post.await_count == 2
    # La segunda petición debe llevar el token NUEVO.
    second_call = mock_request.await_args_list[1]
    assert second_call.kwargs["headers"]["Authorization"] == "TOKEN-NEW"


@pytest.mark.asyncio
async def test_create_ticket_returns_pending_when_not_configured(monkeypatch):
    monkeypatch.setattr("app.services.aranda_service.settings.ARANDA_BASE_URL", "")
    service = ArandaService()

    result = await service.create_ticket(FakeConversation(), FakeUser(), "Caso", "Desc")

    assert result["created"] is False
    assert result["pending_configuration"] is True
    assert result["ticket_id"].startswith("BOTIQ-PENDING-")