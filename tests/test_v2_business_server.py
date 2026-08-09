"""Business REST API + MCP 组合入口回归。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from business import server


def test_business_server_exposes_mcp_without_redirect() -> None:
    """MCP 必须保持标准 /mcp 路径，不能被重定向到 /mcp/。"""
    app = server.create_app()
    with TestClient(app, follow_redirects=False) as client:
        response = client.post("/mcp", json={})

    assert response.status_code != 404
    assert response.status_code != 307


def test_business_api_v2_endpoints() -> None:
    """验证：/api/v2/* REST 端点注册正确。"""
    app = server.create_app()
    schema = app.openapi()
    paths = sorted(schema["paths"].keys())

    # 必须存在的核心端点
    required = [
        "/api/v2/health",
        "/api/v2/readiness",
        "/api/v2/auth/login",
        "/api/v2/auth/register",
        "/api/v2/users/me",
        "/api/v2/farms/my",
        "/api/v2/dashboard",
        "/api/v2/workers",
        "/api/v2/crop-cycles",
        "/api/v2/crop-templates",
        "/api/v2/farm-logs",
        "/api/v2/work-orders",
        "/api/v2/cost-records",
        "/api/v2/debts",
        "/api/v2/weather",
        "/api/v2/locations/search",
    ]
    for p in required:
        assert p in paths, f"Missing endpoint: {p}"


def test_business_api_returns_structured_auth_error() -> None:
    app = server.create_app()
    with TestClient(app) as client:
        response = client.get("/api/v2/users/me")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"
    assert response.json()["detail"]["meta"]["path"] == "/api/v2/users/me"
