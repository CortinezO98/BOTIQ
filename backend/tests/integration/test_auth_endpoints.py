"""Tests de integración — endpoints de auth."""
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_chat_sin_auth_401(client):
    r = await client.post("/api/v1/chat/message", json={"message": "Hola"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_dashboard_sin_auth_401(client):
    r = await client.get("/api/v1/dashboard/metrics")
    assert r.status_code == 401
