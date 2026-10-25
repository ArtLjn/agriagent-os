"""管理端提示词与真实 Token 聚合接口回归。"""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent import prompts
from agent.api import admin_prompts, admin_tokens, api_router
from agent.platforms.persistence.mongo import token_stats
from agent.plugins import PluginScan


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(api_router)
    with TestClient(app) as value:
        yield value


@pytest.fixture
def admin(monkeypatch):
    for module in (admin_prompts, admin_tokens):
        monkeypatch.setattr(
            module, "parse_identity", lambda _: {"role": "admin", "scope": "admin:*"}
        )


@pytest.mark.parametrize(
    "path",
    [
        "prompts",
        "stats/tokens",
        "stats/tokens/daily?date=2026-10-23",
        "stats/tokens/hourly",
    ],
)
def test_auth_required(client, path):
    assert client.get(f"/api/v2/admin/{path}").status_code == 401


def test_regular_user_denied(client, monkeypatch):
    for module in (admin_prompts, admin_tokens):
        monkeypatch.setattr(
            module, "parse_identity", lambda _: {"role": "user", "scope": "farm:read"}
        )
    assert client.get("/api/v2/admin/prompts").status_code == 403
    assert client.post("/api/v2/admin/prompts/reload").status_code == 403
    assert client.get("/api/v2/admin/stats/tokens").status_code == 403


def test_prompt_reports_cached_version_and_reload(client, admin, monkeypatch, tmp_path):
    monkeypatch.setattr(prompts, "_PROMPTS_DIR", tmp_path)
    monkeypatch.setattr(prompts, "_SYSTEM_PROMPT_PATH", tmp_path / "system.md")
    monkeypatch.setattr(prompts, "_cache", {})
    source = tmp_path / "system.md"
    source.write_text("系统提示词 {保持原文}")
    item = client.get("/api/v2/admin/prompts").json()["items"][0]
    assert item["content"] == "系统提示词 {保持原文}"
    assert item["active"] is True
    source.write_text("新内容")
    assert client.get("/api/v2/admin/prompts").json()["items"][0] == item
    assert client.post("/api/v2/admin/prompts/reload").status_code == 200
    updated = client.get("/api/v2/admin/prompts").json()["items"][0]
    assert updated["content"] == "新内容"
    assert updated["version"] != item["version"]


def test_prompt_preview_switches_business_without_activating_it(
    client, admin, monkeypatch, tmp_path
):
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "platform_note.md").write_text("平台提示词", encoding="utf-8")
    lab_prompt = tmp_path / "lab-system.md"
    lab_prompt.write_text("实验业务提示词", encoding="utf-8")
    monkeypatch.setattr(prompts, "_PROMPTS_DIR", prompts_dir)
    monkeypatch.setattr(prompts, "_cache", {})
    monkeypatch.setattr(
        admin_prompts.settings.plugins,
        "manifest",
        SimpleNamespace(name="farm"),
    )
    monkeypatch.setattr(
        admin_prompts,
        "list_plugins",
        lambda _root: [
            PluginScan(
                name="farm",
                manifest=SimpleNamespace(system_prompt_path=tmp_path / "farm.md"),
            ),
            PluginScan(
                name="lab",
                manifest=SimpleNamespace(system_prompt_path=lab_prompt),
            ),
        ],
    )

    response = client.get("/api/v2/admin/prompts?business=lab")

    assert response.status_code == 200
    data = response.json()
    assert data["business"] == "lab"
    assert data["active_business"] == "farm"
    system = next(item for item in data["items"] if item["name"] == "system")
    assert system["content"] == "实验业务提示词"
    assert system["active"] is False
    assert system["scope"] == "business"
    assert system["business"] == "lab"
    platform = next(
        item for item in data["items"] if item["name"] == "platform_note"
    )
    assert platform["scope"] == "platform"
    assert platform["business"] is None


def test_prompt_preview_rejects_unknown_or_invalid_business(
    client, admin, monkeypatch
):
    monkeypatch.setattr(admin_prompts, "list_plugins", lambda _root: [])
    missing = client.get("/api/v2/admin/prompts?business=missing")
    assert missing.status_code == 404
    assert missing.json()["detail"]["code"] == "business_not_found"

    monkeypatch.setattr(
        admin_prompts,
        "list_plugins",
        lambda _root: [
            PluginScan(
                name="broken",
                manifest=None,
                error_code="plugin_manifest_unknown_fields",
            )
        ],
    )
    broken = client.get("/api/v2/admin/prompts?business=broken")
    assert broken.status_code == 409
    assert broken.json()["detail"]["code"] == "business_manifest_invalid"


def test_prompt_reload_rejects_inactive_business(client, admin, monkeypatch):
    monkeypatch.setattr(
        admin_prompts.settings.plugins,
        "manifest",
        SimpleNamespace(name="farm"),
    )
    monkeypatch.setattr(
        admin_prompts,
        "list_plugins",
        lambda _root: [
            PluginScan(
                name="lab",
                manifest=SimpleNamespace(system_prompt_path=__file__),
            )
        ],
    )

    response = client.post("/api/v2/admin/prompts/reload?business=lab")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "business_not_active"


def test_pipeline_uses_beijing_bounds_and_llm_only():
    pipeline = token_stats.build_pipeline(
        date(2026, 10, 23), date(2026, 10, 23), "user-1", "model-1"
    )
    match = pipeline[0]["$match"]
    assert match["created_at"] == {
        "$gte": datetime(2026, 10, 22, 16, tzinfo=UTC),
        "$lt": datetime(2026, 10, 23, 16, tzinfo=UTC),
    }
    assert match["node_type"] == "llm_call"
    assert match["token_usage"] == {"$type": "object"}
    assert match["user_id"] == "user-1"
    assert match["node_name"] == "model-1"
    assert (
        pipeline[1]["$group"]["_id"]["hour"]["$dateToString"]["timezone"]
        == "Asia/Shanghai"
    )


def test_stats_aggregate_models_and_forward_filters(client, admin, monkeypatch):
    rows = [
        {
            "date": "2026-10-23",
            "hour": "08",
            "user_id": "u",
            "model": model,
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "request_count": 1,
        }
        for model in ("a", "a", "b")
    ]
    query = AsyncMock(return_value=rows)
    monkeypatch.setattr(token_stats, "hourly_usage", query)
    monkeypatch.setattr(admin_tokens, "beijing_today", lambda: date(2026, 10, 23))
    result = client.get("/api/v2/admin/stats/tokens?days=7&user_id=u").json()
    assert result["total_tokens"] == 45
    assert result["total_requests"] == 3
    assert result["by_model"]["a"]["total_tokens"] == 30
    query.assert_awaited_with(date(2026, 10, 17), date(2026, 10, 23), "u", None)
    result = client.get(
        "/api/v2/admin/stats/tokens/hourly?start_date=2026-10-23&end_date=2026-10-23&model=a"
    ).json()
    assert result["items"] == rows
    assert len(result["hours"]) == 24
    query.assert_awaited_with(date(2026, 10, 23), date(2026, 10, 23), None, "a")
    assert (
        client.get("/api/v2/admin/stats/tokens/daily?date=2026-10-23").json()["items"][
            0
        ]["total_tokens"]
        == 30
    )


@pytest.mark.parametrize("query", ["days=0", "days=94"])
def test_summary_range_validation(client, admin, query):
    assert client.get(f"/api/v2/admin/stats/tokens?{query}").status_code == 422


def test_invalid_range_does_not_query_store(client, admin, monkeypatch):
    query = AsyncMock()
    monkeypatch.setattr(token_stats, "hourly_usage", query)
    for start, end in [("2026-10-24", "2026-10-23"), ("2026-01-01", "2026-10-23")]:
        assert (
            client.get(
                f"/api/v2/admin/stats/tokens/hourly?start_date={start}&end_date={end}"
            ).status_code
            == 422
        )
    query.assert_not_awaited()


def test_empty_and_unavailable_are_distinct(client, admin, monkeypatch):
    monkeypatch.setattr(token_stats, "hourly_usage", AsyncMock(return_value=[]))
    assert client.get("/api/v2/admin/stats/tokens").json()["total_tokens"] == 0
    monkeypatch.setattr(
        token_stats,
        "hourly_usage",
        AsyncMock(side_effect=token_stats.TokenStatsUnavailable()),
    )
    result = client.get("/api/v2/admin/stats/tokens")
    assert result.status_code == 503
    assert result.json()["detail"]["code"] == "token_stats_unavailable"


@pytest.mark.asyncio
async def test_store_uses_aggregate_without_loading_trace_payloads(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock

    async def rows():
        yield {
            "_id": {"date": "2026-10-23", "hour": "09", "user_id": "u", "model": "a"},
            "total_tokens": 12,
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "request_count": 1,
        }

    collection = Mock()
    collection.aggregate.return_value = rows()
    name = token_stats.settings.mongodb.collections.get("trace_records", "traceRecords")
    monkeypatch.setattr(token_stats.settings.mongodb, "enabled", True)
    monkeypatch.setattr(
        token_stats,
        "get_collection",
        lambda: SimpleNamespace(database={name: collection}),
    )
    result = await token_stats.hourly_usage(
        date(2026, 10, 23), date(2026, 10, 23), None, None
    )
    assert result[0]["model"] == "a"
    assert result[0]["total_tokens"] == 12
    assert "_id" not in result[0]
    assert (
        collection.aggregate.call_args.kwargs["maxTimeMS"]
        == token_stats.QUERY_TIMEOUT_MS
    )


@pytest.mark.asyncio
async def test_disabled_store_is_unavailable(monkeypatch):
    monkeypatch.setattr(token_stats.settings.mongodb, "enabled", False)
    with pytest.raises(token_stats.TokenStatsUnavailable):
        await token_stats.hourly_usage(
            date(2026, 10, 23), date(2026, 10, 23), None, None
        )
