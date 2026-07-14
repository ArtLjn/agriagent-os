"""Agent App 技能列表 API 测试。"""

from fastapi.testclient import TestClient

from app.main import app
from tests.api.auth_helpers import (
    auth_override_scope,
    ensure_regular_user,
    regular_headers,
)


def test_agent_skills_returns_app_safe_skill_cards(db_session) -> None:
    """普通 App 用户可读取展示用技能列表，不暴露管理员调试字段。"""
    ensure_regular_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).get("/agent/skills", headers=regular_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == len(data["items"])
    assert data["items"]

    first = data["items"][0]
    assert {
        "key",
        "title",
        "description",
        "summary",
        "details",
        "examples",
        "category",
        "icon",
        "icon_color",
        "recommended",
        "enabled",
    } <= set(first)
    assert "parameters_schema" not in first
    assert "metadata" not in first

    farm_status = next(
        item for item in data["items"] if item["key"] == "get_farm_status"
    )
    assert farm_status["summary"] == "汇总待办、近期农事、花费和天气。"
    assert "当前农场综合状态" in farm_status["details"]
    assert "今天农场怎么样" in farm_status["examples"]


def test_agent_skills_only_returns_app_level_capabilities(db_session) -> None:
    """App 技能列表只展示产品能力入口，不暴露内部拆分工具。"""
    ensure_regular_user(db_session)
    with auth_override_scope(app):
        resp = TestClient(app).get("/agent/skills", headers=regular_headers())

    assert resp.status_code == 200
    data = resp.json()
    keys = {item["key"] for item in data["items"]}

    assert keys == {
        "get_farm_status",
        "manage_cost",
        "manage_farm_logs",
        "manage_wages",
        "manage_crop_cycle",
        "get_weather_forecast",
        "manage_user_settings",
    }
    assert "create_crop_cycle" not in keys
    assert "create_cost_record" not in keys
    assert "get_cost_analytics" not in keys
    assert "get_cost_summary" not in keys
    assert "get_debt_summary" not in keys
    assert "settle_debt" not in keys
    assert "delete_cost_record" not in keys
    assert "manage_cost_categories" not in keys


def test_agent_skills_rejects_anonymous_user(db_session) -> None:
    """匿名用户不能读取 App 技能列表。"""
    with auth_override_scope(app):
        resp = TestClient(app).get("/agent/skills")

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"
