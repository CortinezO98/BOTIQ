"""
Pruebas de integración para el flujo de sesión por cookie httpOnly +
refresh token (agregado en 1.6.0). Cada test crea su propio usuario con
email único para no depender de datos previos ni de limpieza manual de DB,
siguiendo el mismo patrón que test_auth_endpoints.py (AsyncClient contra
la app real, sin mocks).

Nota: si corres esto localmente con RATE_LIMIT_ENABLED=true, varias
corridas seguidas en menos de un minuto podrían acercarse al límite de
LOGIN_RATE_LIMIT (10/minute) porque /auth/register también lo usa. En CI
ya viene con RATE_LIMIT_ENABLED=false (ver .github/workflows/ci.yml).
"""
import uuid

import pytest
from httpx import AsyncClient

from app.main import app
from app.core.config import settings


def _unique_email() -> str:
    # Dominio iq-online.com a propósito: coincide con el que se usará para
    # restringir /auth/register (próximo cambio del backlog), así estos
    # tests no se rompen cuando esa restricción se active.
    return f"test_{uuid.uuid4().hex[:10]}@iq-online.com"


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


async def _register_and_login(client: AsyncClient) -> str:
    email = _unique_email()
    password = "Test1234!"

    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User", "password": password},
    )
    assert r.status_code == 201, r.text

    r = await client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert r.status_code == 200, r.text
    return email


@pytest.mark.asyncio
async def test_login_sets_httponly_cookies(client):
    await _register_and_login(client)

    cookie_names = {c.name for c in client.cookies.jar}
    assert settings.ACCESS_TOKEN_COOKIE_NAME in cookie_names
    assert settings.REFRESH_TOKEN_COOKIE_NAME in cookie_names


@pytest.mark.asyncio
async def test_me_works_via_cookie_without_authorization_header(client):
    await _register_and_login(client)

    # Sin header Authorization: get_current_user debe resolver por cookie.
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["email"]


@pytest.mark.asyncio
async def test_refresh_rotates_token_and_invalidates_previous_one(client):
    await _register_and_login(client)

    old_refresh_cookie = client.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    assert old_refresh_cookie

    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200, r.text

    new_refresh_cookie = client.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    assert new_refresh_cookie
    assert new_refresh_cookie != old_refresh_cookie, "El refresh token debe rotar, no reutilizarse"

    # El refresh token viejo ya fue revocado en la rotación: no debe servir más.
    client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, old_refresh_cookie)
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client):
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_session(client):
    await _register_and_login(client)

    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200

    # El refresh token quedó revocado: ya no debe poder renovar sesión.
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_register_rejects_non_corporate_domain(client):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"test_{uuid.uuid4().hex[:10]}@gmail.com",
            "full_name": "Test User",
            "password": "Test1234!",
        },
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_login_with_uppercase_email_matches_lowercase_registered_user(client):
    """Regresión: antes de 1.5.0, auth.register no normalizaba el email,
    así que un login con mayúsculas podía no encontrar al usuario."""
    email = _unique_email()
    password = "Test1234!"

    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "full_name": "Test User", "password": password},
    )
    assert r.status_code == 201

    r = await client.post(
        "/api/v1/auth/login",
        data={"username": email.upper(), "password": password},
    )
    assert r.status_code == 200, r.text