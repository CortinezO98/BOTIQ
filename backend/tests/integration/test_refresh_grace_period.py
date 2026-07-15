import asyncio
import uuid

import pytest
from httpx import AsyncClient

from app.main import app
from app.core.config import settings
from app.core.security import hash_password
from app.core.roles import UserRole
from app.db.session import AsyncSessionLocal
from app.models.user import User
from app.models import conversation as _conversation_stub  # noqa: F401


def _unique_email() -> str:
    return f"user_{uuid.uuid4().hex[:10]}@iq-online.com"


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


async def _create_user(email: str, password: str) -> User:
    async with AsyncSessionLocal() as db:
        user = User(
            email=email,
            full_name="Usuario de prueba",
            hashed_password=hash_password(password),
            role=UserRole.EMPLOYEE,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


@pytest.mark.asyncio
async def test_concurrent_refresh_with_same_old_cookie_both_succeed(client):
    """
    Regresión real: reportada por el usuario tras navegar rápido entre
    varias pantallas del dashboard (o con varias pestañas abiertas), donde
    TODAS las llamadas a la API devolvían 401 en cascada, incluyendo
    /auth/me y /auth/refresh, con sesión activa real.

    Simula el escenario: dos peticiones a /auth/refresh casi simultáneas
    usando la MISMA cookie de refresh token (como pasaría con dos pestañas,
    o varias llamadas paralelas del frontend que expiran su access token
    casi al mismo tiempo). Antes del fix, la primera rotaba el token con
    éxito y la segunda quedaba rechazada con 401 porque el token ya estaba
    revocado -- aunque la sesión fuera legítima.
    """
    email = _unique_email()
    password = "Test1234!"
    await _create_user(email, password)

    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200
    old_refresh_cookie = client.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    assert old_refresh_cookie

    # Dos clientes HTTP independientes (simulan dos pestañas) mandando la
    # MISMA cookie de refresh vieja, casi al mismo tiempo.
    async with AsyncClient(app=app, base_url="http://test") as client_a, \
               AsyncClient(app=app, base_url="http://test") as client_b:
        client_a.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, old_refresh_cookie)
        client_b.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, old_refresh_cookie)

        r_a, r_b = await asyncio.gather(
            client_a.post("/api/v1/auth/refresh"),
            client_b.post("/api/v1/auth/refresh"),
        )

    # Antes del fix: una de las dos fallaba con 401. Ahora ambas deben
    # completarse con éxito -- ninguna sesión legítima debe perderse por
    # una ráfaga de llamadas concurrentes.
    assert r_a.status_code == 200, r_a.text
    assert r_b.status_code == 200, r_b.text


@pytest.mark.asyncio
async def test_reuse_outside_grace_period_is_rejected(client):
    """El período de gracia tiene un límite real: pasado ese tiempo, un
    token ya rotado debe seguir siendo rechazado (si no, la rotación no
    protegería contra un token robado)."""
    email = _unique_email()
    password = "Test1234!"
    await _create_user(email, password)

    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    old_refresh_cookie = client.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)

    # Primer refresh: rota el token (queda con rotated_at = ahora).
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 200

    # Truco para probar el límite del período de gracia sin dormir el test
    # real: bajamos la gracia a 0 segundos ANTES del segundo intento.
    original_grace = settings.REFRESH_TOKEN_GRACE_SECONDS
    settings.REFRESH_TOKEN_GRACE_SECONDS = 0
    try:
        await asyncio.sleep(0.05)  # asegura que quede fuera de una ventana de 0s
        client.cookies.set(settings.REFRESH_TOKEN_COOKIE_NAME, old_refresh_cookie)
        r = await client.post("/api/v1/auth/refresh")
        assert r.status_code == 401
    finally:
        settings.REFRESH_TOKEN_GRACE_SECONDS = original_grace


@pytest.mark.asyncio
async def test_logout_is_still_immediate_not_subject_to_grace_period(client):
    """El período de gracia es SOLO para rotación normal. logout() sigue
    revocando de inmediato -- no debe quedar una ventana donde una sesión
    cerrada explícitamente todavía funcione."""
    email = _unique_email()
    password = "Test1234!"
    await _create_user(email, password)

    r = await client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200

    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200

    # Inmediatamente después del logout, sin esperar ningún período de
    # gracia, el refresh debe fallar.
    r = await client.post("/api/v1/auth/refresh")
    assert r.status_code == 401