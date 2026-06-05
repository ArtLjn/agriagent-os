"""Admin API 鉴权分类行为测试。"""

from fastapi.testclient import TestClient

from app.main import app
from tests.api.auth_helpers import auth_override_scope


def test_admin_skills_rejects_anonymous_with_real_auth(db_session):
    """匿名访问管理接口返回 401。"""
    with auth_override_scope(app):
        resp = TestClient(app).get("/admin/skills")

    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "AUTH_MISSING_TOKEN"
