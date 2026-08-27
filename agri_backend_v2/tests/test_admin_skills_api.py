"""管理员 Skill 列表接口测试。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api import admin_skills, api_router
from shared.api_response import install_api_exception_handlers


def _client() -> TestClient:
    app = FastAPI()
    install_api_exception_handlers(app)
    app.include_router(api_router)
    return TestClient(app)


def test_admin_skill_list_requires_authentication() -> None:
    with _client() as client:
        response = client.get("/api/v2/admin/skills")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "missing_authorization"


def test_regular_user_cannot_list_skills(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_skills,
        "parse_identity",
        lambda _authorization: {
            "role": "user",
            "scope": "farm:read",
        },
    )

    with _client() as client:
        response = client.get(
            "/api/v2/admin/skills", headers={"Authorization": "Bearer user-token"}
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "permission_denied"


def test_admin_skill_list_returns_aggregate_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        admin_skills,
        "parse_identity",
        lambda _authorization: {
            "role": "admin",
            "scope": "admin:*",
        },
    )
    monkeypatch.setattr(
        admin_skills.loader,
        "load_aggregate_skills",
        lambda: [
            admin_skills.loader._build_mcp_skill(
                {
                    "name": "z_skill",
                    "kind": "mcp",
                    "mcp_tool": "business.z_skill",
                    "risk_level": "read",
                    "description": "测试 Skill",
                    "parameters": {
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                    },
                }
            )
        ],
    )

    with _client() as client:
        response = client.get(
            "/api/v2/admin/skills", headers={"Authorization": "Bearer admin-token"}
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "name": "z_skill",
                "description": "测试 Skill",
                "parameters_schema": {
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                },
                "metadata": {
                    "enabled": True,
                    "disabled_reason": None,
                    "permission_level": "read",
                    "risk_level": "low",
                    "context_dependencies": [],
                    "cache_invalidation": [],
                    "confirmation_schema": {},
                    "evaluation_tags": [],
                    "metadata_incomplete": True,
                },
                "status": "active",
            }
        ],
        "total": 1,
        "summary": {"total": 1, "enabled": 1, "disabled": 0, "admin_only": 0},
    }
