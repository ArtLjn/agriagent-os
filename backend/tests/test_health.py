"""健康检查路由测试。"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.bootstrap.routes import register_routes


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_health_includes_mongo_health(monkeypatch):
    async def fake_mongo_health():
        return {
            "status": "ok",
            "database": "farm_manager_docs",
            "code": "mongo_ping_ok",
        }

    monkeypatch.setattr("app.bootstrap.routes.check_mongo_health", fake_mongo_health)
    app = FastAPI()
    register_routes(app)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        trust_env=False,
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mongo": {
            "status": "ok",
            "database": "farm_manager_docs",
            "code": "mongo_ping_ok",
        },
    }


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_health_reports_degraded_when_mongo_health_fails(monkeypatch):
    async def fake_mongo_health():
        return {
            "status": "error",
            "database": "farm_manager_docs",
            "code": "mongo_ping_failed",
            "context": {
                "error": "cannot connect mongodb://user:***@mongo.internal:27017/db"
            },
        }

    monkeypatch.setattr("app.bootstrap.routes.check_mongo_health", fake_mongo_health)
    app = FastAPI()
    register_routes(app)

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        trust_env=False,
    ) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["mongo"]["code"] == "mongo_ping_failed"
    assert "plain-secret" not in str(data)
