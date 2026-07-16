from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.roles import UserRole
from app.services.aranda_tracking_service import ArandaTrackingService


def test_extracts_composed_reference():
    service = ArandaTrackingService()
    ref = service.extract_reference("Seguimiento RF-886064-1-674642")
    assert ref is not None
    assert ref.prefix == "RF"
    assert ref.global_id == 886064
    assert ref.project_id == 1
    assert ref.id_by_project == 674642
    assert ref.item_type == 4
    assert ref.candidates == ["RF-886064-1-674642", 886064]


def test_tracking_intent_does_not_capture_normal_support_question():
    service = ArandaTrackingService()
    assert service.is_tracking_request("El portal me muestra error 503") is False
    assert service.is_tracking_request("Cómo va mi ticket RF-886064-1-674642") is True
    assert service.is_tracking_request("RF-886064-1-674642") is True


def test_private_notes_and_urls_are_filtered_for_employee():
    service = ArandaTrackingService()
    history = service._filter_history(
        [
            {"Description": "Pública", "IsPrivate": False},
            {"Description": "Interna", "IsPrivate": True},
        ],
        UserRole.EMPLOYEE,
    )
    assert [row["Description"] for row in history] == ["Pública"]

    files = service._filter_files(
        [
            {"Name": "publico.pdf", "IsPublic": True, "Url": "https://host/?token=SECRETO"},
            {"Name": "interno.pdf", "IsPublic": False, "Url": "https://host/?token=OTRO"},
        ],
        UserRole.EMPLOYEE,
    )
    assert files == [{"Name": "publico.pdf", "Size": 0, "Created": None, "IsPublic": True}]
    assert "Url" not in files[0]


def test_employee_must_own_external_ticket():
    service = ArandaTrackingService()
    ref = service.extract_reference("RF-886064-1-674642")
    conversation = SimpleNamespace(aranda_ticket_id=None)
    current_user = SimpleNamespace(role=UserRole.EMPLOYEE)

    ok, _ = service._validate_access(
        current_user=current_user,
        conversation=conversation,
        reference=ref,
        case={"ProjectId": 1, "CustomerId": 100, "AuthorId": 101},
        user_matches=[{"Id": 999}],
    )
    assert ok is False

    ok, _ = service._validate_access(
        current_user=current_user,
        conversation=conversation,
        reference=ref,
        case={"ProjectId": 1, "CustomerId": 100, "AuthorId": 101},
        user_matches=[{"Id": 100}],
    )
    assert ok is True


def test_aranda_date_is_converted_to_bogota(monkeypatch):
    service = ArandaTrackingService()
    # 2021-01-01 00:00 UTC -> 2020-12-31 19:00 Bogotá
    value = service._format_date("/Date(1609459200000-0500)/")
    assert value.startswith("31/12/2020 07:00")
