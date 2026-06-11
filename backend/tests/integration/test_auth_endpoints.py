"""
Tests de integración para los endpoints de autenticación.
Requieren una BD de test configurada (ver pytest.ini).
"""

import pytest
from httpx import AsyncClient
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_register_new_user(client):
    """Registrar un usuario nuevo retorna 201 con los datos del usuario."""
    response = await client.post("/api/v1/auth/register", json={
        "email": "test@empresa.com",
        "full_name": "Usuario Test",
        "password": "Password123",
        "role": "employee",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@empresa.com"
    assert data["role"] == "employee"
    assert "hashed_password" not in data  # Nunca exponer el hash


@pytest.mark.asyncio
async def test_register_duplicate_email_fails(client):
    """Registrar dos veces el mismo email retorna 400."""
    payload = {
        "email": "duplicate@empresa.com",
        "full_name": "Usuario",
        "password": "Password123",
        "role": "employee",
    }
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_returns_token(client):
    """Login con credenciales correctas retorna JWT."""
    # Registrar primero
    await client.post("/api/v1/auth/register", json={
        "email": "login_test@empresa.com",
        "full_name": "Login Test",
        "password": "MiPassword123",
        "role": "employee",
    })

    # Login
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "login_test@empresa.com", "password": "MiPassword123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login_test@empresa.com"


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    """Login con contraseña incorrecta retorna 401."""
    response = await client.post(
        "/api/v1/auth/login",
        data={"username": "noexiste@empresa.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_chat_without_auth_returns_401(client):
    """Enviar mensaje sin token retorna 401."""
    response = await client.post("/api/v1/chat/message", json={
        "message": "Hola"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_employee_returns_403(client):
    """Un empleado no puede acceder al dashboard."""
    # Registrar y hacer login como empleado
    await client.post("/api/v1/auth/register", json={
        "email": "emp@empresa.com",
        "full_name": "Empleado",
        "password": "Password123",
        "role": "employee",
    })
    login_resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "emp@empresa.com", "password": "Password123"},
    )
    token = login_resp.json()["access_token"]

    # Intentar acceder al dashboard
    response = await client.get(
        "/api/v1/dashboard/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
