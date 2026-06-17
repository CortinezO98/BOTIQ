import pytest
from httpx import AsyncClient
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as c: yield c

@pytest.mark.asyncio
async def test_health(client):
    r=await client.get("/health"); assert r.status_code==200

@pytest.mark.asyncio
async def test_chat_401(client):
    r=await client.post("/api/v1/chat/message",data={"message":"Hola"}); assert r.status_code==401

@pytest.mark.asyncio
async def test_dashboard_401(client):
    r=await client.get("/api/v1/dashboard/metrics"); assert r.status_code==401


