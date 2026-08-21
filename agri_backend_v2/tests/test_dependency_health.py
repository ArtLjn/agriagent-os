"""Mongo/Redis 不可用时的结构化健康状态测试。"""

from __future__ import annotations

import pytest

from agent.api import health
from agent.platforms.persistence.mongo import chat_store


@pytest.mark.asyncio
async def test_mongo_status_distinguishes_disabled_from_ready(monkeypatch) -> None:
    monkeypatch.setattr(chat_store.settings.mongodb, "enabled", False)

    result = await chat_store.status()

    assert result == {
        "enabled": False,
        "reachable": False,
        "source_status": "unavailable",
        "code": "mongo_not_configured",
    }


@pytest.mark.asyncio
async def test_health_reports_mongo_degradation(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "redis_status",
        lambda: _async_value({"enabled": True, "reachable": True}),
    )
    monkeypatch.setattr(
        health.chat_store,
        "status",
        lambda: _async_value(
            {
                "enabled": True,
                "reachable": False,
                "source_status": "unavailable",
                "code": "mongo_unavailable",
            }
        ),
    )
    monkeypatch.setattr(health, "pending_approval_count", lambda: _async_value(0))
    monkeypatch.setattr(health, "get_client", lambda: None)

    result = await health.health()

    assert result["status"] == "degraded"
    assert result["mongo"]["code"] == "mongo_unavailable"


async def _async_value(value):
    return value
