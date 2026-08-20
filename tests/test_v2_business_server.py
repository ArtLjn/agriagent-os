"""Business REST API + MCP 组合入口回归。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from business import server
from business.mcp_app import mcp


def test_business_server_exposes_mcp_without_redirect() -> None:
    """MCP 必须保持标准 /mcp 路径，不能被重定向到 /mcp/。"""
    app = server.create_app()
    with TestClient(app, follow_redirects=False) as client:
        response = client.post("/mcp", json={})

    assert response.status_code != 404
    assert response.status_code != 307


def test_business_api_v2_endpoints() -> None:
    """验证：/api/agri_backend_v2/* REST 端点注册正确。"""
    app = server.create_app()
    schema = app.openapi()
    paths = sorted(schema["paths"].keys())

    # 必须存在的核心端点
    required = [
        "/api/agri_backend_v2/health",
        "/api/agri_backend_v2/readiness",
        "/api/agri_backend_v2/auth/login",
        "/api/agri_backend_v2/auth/register",
        "/api/agri_backend_v2/users/me",
        "/api/agri_backend_v2/users/me/settings",
        "/api/agri_backend_v2/farms/my",
        "/api/agri_backend_v2/dashboard",
        "/api/agri_backend_v2/workers",
        "/api/agri_backend_v2/crop-cycles",
        "/api/agri_backend_v2/crop-templates",
        "/api/agri_backend_v2/farm-logs",
        "/api/agri_backend_v2/work-orders",
        "/api/agri_backend_v2/cost-records",
        "/api/agri_backend_v2/debts",
        "/api/agri_backend_v2/weather",
        "/api/agri_backend_v2/locations/search",
    ]
    for p in required:
        assert p in paths, f"Missing endpoint: {p}"


@pytest.mark.asyncio
async def test_business_mcp_registers_user_settings_tool() -> None:
    tools = await mcp.list_tools()

    assert any(tool.name == "manage_user_settings" for tool in tools)


def test_business_api_returns_structured_auth_error() -> None:
    app = server.create_app()
    with TestClient(app) as client:
        response = client.get("/api/agri_backend_v2/users/me")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"
    assert response.json()["detail"]["meta"]["path"] == "/api/agri_backend_v2/users/me"
