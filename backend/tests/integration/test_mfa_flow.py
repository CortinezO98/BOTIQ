import uuid

import pyotp
import pytest
from httpx import AsyncClient

from app.main import app
from app.core.config import settings
from app.core.security import hash_password
from app.core.roles import UserRole
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.core import mfa as mfa_core


def _unique_email() -> str:
    return f"admin_{uuid.uuid4().hex[:10]}@iq-online.com"


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


async def _create_admin_user(email: str, password: str) -> User:
    async with AsyncSessionLocal() as db:
        user = User(
            email=email,
            full_name="Admin de prueba",
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@pytest.mark.asyncio
async def test_login_without_mfa_enabled_returns_session_directly(client):
    email = _unique_email()
    password = "Test1234!"
    await _create_admin_user(email, password)

    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["user"]["email"] == email
    assert settings.ACCESS_TOKEN_COOKIE_NAME in {c.name for c in client.cookies.jar}


@pytest.mark.asyncio
async def test_full_mfa_enrollment_and_login_flow(client):
    email = _unique_email()
    password = "Test1234!"
    await _create_admin_user(email, password)

    # 1. Login normal para tener sesión (necesaria para /mfa/setup)
    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200

    # 2. Iniciar enrolamiento MFA
    r = await client.post("/api/v1/auth/mfa/setup")
    assert r.status_code == 200, r.text
    setup_data = r.json()
    assert setup_data["secret"]
    assert setup_data["otpauth_uri"].startswith("otpauth://totp/")
    assert len(setup_data["qr_code_base64"]) > 100

    # 3. Confirmar con un código TOTP real generado a partir del secreto
    totp = pyotp.TOTP(setup_data["secret"])
    valid_code = totp.now()
    r = await client.post("/api/v1/auth/mfa/confirm", json={"code": valid_code})
    assert r.status_code == 200, r.text
    assert r.json()["mfa_enabled"] is True

    # 4. Cerrar sesión y volver a loguear: ahora debe pedir MFA, no dar sesión directa
    await client.post("/api/v1/auth/logout")
    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200
    body = r.json()
    assert body.get("mfa_required") is True
    assert "mfa_challenge_token" in body
    # Importante: NO debe haber seteado cookie de sesión todavía
    assert settings.ACCESS_TOKEN_COOKIE_NAME not in {c.name for c in client.cookies.jar}

    # 5. Verificar con un código TOTP real -> recién ahí se completa la sesión
    valid_code_2 = totp.now()
    r = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_challenge_token": body["mfa_challenge_token"], "code": valid_code_2},
    )
    assert r.status_code == 200, r.text
    assert "access_token" in r.json()
    assert settings.ACCESS_TOKEN_COOKIE_NAME in {c.name for c in client.cookies.jar}


@pytest.mark.asyncio
async def test_mfa_verify_rejects_wrong_code(client):
    email = _unique_email()
    password = "Test1234!"
    await _create_admin_user(email, password)

    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    r = await client.post("/api/v1/auth/mfa/setup")
    setup_data = r.json()
    totp = pyotp.TOTP(setup_data["secret"])
    await client.post("/api/v1/auth/mfa/confirm", json={"code": totp.now()})
    await client.post("/api/v1/auth/logout")

    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    challenge_token = r.json()["mfa_challenge_token"]

    r = await client.post(
        "/api/v1/auth/mfa/verify",
        json={"mfa_challenge_token": challenge_token, "code": "000000"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_mfa_disable_requires_password_and_code(client):
    email = _unique_email()
    password = "Test1234!"
    await _create_admin_user(email, password)

    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    r = await client.post("/api/v1/auth/mfa/setup")
    setup_data = r.json()
    totp = pyotp.TOTP(setup_data["secret"])
    await client.post("/api/v1/auth/mfa/confirm", json={"code": totp.now()})

    # Password incorrecto -> rechazado
    r = await client.post("/api/v1/auth/mfa/disable", json={"password": "wrong-pass", "code": totp.now()})
    assert r.status_code == 401

    # Password correcto + código válido -> apagado
    r = await client.post("/api/v1/auth/mfa/disable", json={"password": password, "code": totp.now()})
    assert r.status_code == 200, r.text
    assert r.json()["mfa_enabled"] is False

    # Login vuelve a dar sesión directa (ya no pide MFA)
    await client.post("/api/v1/auth/logout")
    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_mfa_challenge_token_cannot_be_reused_as_access_token(client):
    """Regresión de diseño: un token de desafío MFA no debe servir como
    Authorization Bearer para endpoints protegidos normales."""
    email = _unique_email()
    password = "Test1234!"
    await _create_admin_user(email, password)

    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    r = await client.post("/api/v1/auth/mfa/setup")
    setup_data = r.json()
    totp = pyotp.TOTP(setup_data["secret"])
    await client.post("/api/v1/auth/mfa/confirm", json={"code": totp.now()})
    await client.post("/api/v1/auth/logout")

    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    challenge_token = r.json()["mfa_challenge_token"]

    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {challenge_token}"})
    assert r.status_code == 401