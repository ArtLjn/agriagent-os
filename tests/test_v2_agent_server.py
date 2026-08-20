"""Agent agri_backend_v2 REST 路由注册回归测试。"""

from agent.main import app


def test_agent_v2_routes_keep_ui_and_static_entries() -> None:
    routes = {route.path for route in app.routes}
    assert {"/", "/static", "/api/agri_backend_v2/health", "/api/agri_backend_v2/chat"} <= routes
    assert "/api/agri_backend_v2/conversations" in routes
    assert "/api/agri_backend_v2/dev-users" in routes
    assert "/api/agri_backend_v2/approve" in routes
