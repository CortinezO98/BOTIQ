from datetime import timedelta

import pytest
from fastapi import HTTPException
from jose import jwt
from starlette.requests import Request

from app.core.config import settings
from app.core.security import (
    create_widget_access_token,
    decode_token,
)
from app.core.widget_security import (
    normalize_origin,
    validate_widget_request_context,
)


def _request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/chat/conversations",
        "headers": [
            (key.lower().encode(), value.encode())
            for key, value in headers.items()
        ],
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    }
    return Request(scope)


def test_widget_token_contains_portal_and_origin_claims():
    token = create_widget_access_token(
        user_id="2e126092-8c08-4f00-a381-d47d7ae249b4",
        role="employee",
        portal_id="portal-icetex",
        allowed_origin="https://portal.icetex.gov.co",
        expires_delta=timedelta(minutes=10),
    )

    claims = decode_token(token)

    assert claims["purpose"] == "widget_access"
    assert claims["role"] == "employee"
    assert claims["portal_id"] == "portal-icetex"
    assert claims["allowed_origin"] == "https://portal.icetex.gov.co"
    assert claims["jti"]


def test_widget_context_headers_must_match_token_claims():
    claims = {
        "purpose": "widget_access",
        "portal_id": "portal-icetex",
        "allowed_origin": "https://portal.icetex.gov.co",
    }
    request = _request(
        {
            "X-BOTIQ-Portal-Id": "portal-icetex",
            "X-BOTIQ-Parent-Origin": "https://portal.icetex.gov.co",
        }
    )

    validate_widget_request_context(request, claims)


def test_widget_context_rejects_another_origin():
    claims = {
        "purpose": "widget_access",
        "portal_id": "portal-icetex",
        "allowed_origin": "https://portal.icetex.gov.co",
    }
    request = _request(
        {
            "X-BOTIQ-Portal-Id": "portal-icetex",
            "X-BOTIQ-Parent-Origin": "https://portal-falso.example.com",
        }
    )

    with pytest.raises(HTTPException) as exc:
        validate_widget_request_context(request, claims)

    assert exc.value.status_code == 401


def test_decode_token_rejects_unknown_purpose():
    token = jwt.encode(
        {
            "sub": "2e126092-8c08-4f00-a381-d47d7ae249b4",
            "purpose": "otro_uso",
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(HTTPException):
        decode_token(token)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://Portal.Example.com/", "https://portal.example.com"),
        ("http://localhost:5500", "http://localhost:5500"),
        ("https://example.com:443", "https://example.com"),
    ],
)
def test_normalize_origin(raw, expected):
    assert normalize_origin(raw) == expected

def test_widget_router_imports_and_registers_routes():
    # Regression: with `from __future__ import annotations` in widget.py,
    # SlowAPI wrapped issue_widget_token and FastAPI/Pydantic attempted to
    # resolve the string annotation WidgetTokenRequest in the wrapper's
    # global namespace, causing PydanticUndefinedAnnotation at startup.
    from app.api.v1.routes.widget import router

    paths = {route.path for route in router.routes}
    assert "/token" in paths
    assert "/config" in paths

