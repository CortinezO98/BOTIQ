from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.aranda_service import ArandaService, ArandaSession


@pytest.mark.asyncio
async def test_tracking_bundle_reuses_one_session(monkeypatch):
    service = ArandaService()
    fake_client = object()
    fake_session = ArandaSession(user_id=77, session_id="secret-session")

    class FakeContext:
        async def __aenter__(self):
            return fake_client, fake_session
        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(service, "_authenticated_session", lambda: FakeContext())
    monkeypatch.setattr(
        service,
        "_get_case_with_session",
        AsyncMock(return_value={"Id": 886064, "ComposedId": "RF-886064-1-674642", "ProjectId": 1}),
    )
    monkeypatch.setattr(service, "_list_history_with_session", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_list_files_with_session", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_search_users_with_session", AsyncMock(return_value=[]))

    result = await service.get_ticket_tracking_bundle(
        item_candidates=["RF-886064-1-674642", 886064],
        item_types=[4],
        identity_email="user@iq-online.com",
        project_id=1,
    )

    assert result["resolved_item_id"] == 886064
    assert result["resolved_item_type"] == 4
    service._get_case_with_session.assert_awaited_once()
    service._list_history_with_session.assert_awaited_once()
    service._list_files_with_session.assert_awaited_once()
