"""Auth API 端到端测试。"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.main import app


@pytest.fixture
def client():
    """创建测试客户端，使用完整应用（清除 get_current_user 覆盖，测试真实 JWT 流程）。"""
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestAuthRegister:
    """测试注册接口。"""

    def test_register_success(self, client, clean_db):
        """POST /auth/register 注册成功。"""
        resp = client.post(
            "/auth/register",
            json={"phone": "13800138000", "password": "password123", "nickname": "张三"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["phone"] == "13800138000"
        assert data["user"]["nickname"] == "张三"

    def test_register_invalid_phone(self, client, clean_db):
        """手机号格式错误返回 422。"""
        resp = client.post(
            "/auth/register",
            json={"phone": "123", "password": "password123"},
        )

        assert resp.status_code == 422

    def test_register_short_password(self, client, clean_db):
        """密码少于 8 位返回 422。"""
        resp = client.post(
            "/auth/register",
            json={"phone": "13800138000", "password": "1234567"},
        )

        assert resp.status_code == 422

    def test_register_duplicate_phone(self, client, clean_db):
        """重复注册同一手机号返回 400。"""
        client.post(
            "/auth/register",
            json={"phone": "13800138000", "password": "password123"},
        )
        resp = client.post(
            "/auth/register",
            json={"phone": "13800138000", "password": "password123"},
        )

        assert resp.status_code == 400


class TestAuthLogin:
    """测试登录接口。"""

    def test_login_success(self, client, clean_db):
        """注册后登录成功。"""
        client.post(
            "/auth/register",
            json={"phone": "13800138001", "password": "password123"},
        )
        resp = client.post(
            "/auth/login",
            json={"phone": "13800138001", "password": "password123"},
        )

        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client, clean_db):
        """密码错误返回 401。"""
        client.post(
            "/auth/register",
            json={"phone": "13800138002", "password": "password123"},
        )
        resp = client.post(
            "/auth/login",
            json={"phone": "13800138002", "password": "wrongpassword"},
        )

        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client, clean_db):
        """登录不存在的用户返回 401。"""
        resp = client.post(
            "/auth/login",
            json={"phone": "13800999999", "password": "password123"},
        )

        assert resp.status_code == 401


class TestAuthMe:
    """测试 /auth/me 接口。"""

    def test_get_me_with_token(self, client, clean_db):
        """GET /auth/me 返回当前用户信息。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138003", "password": "password123"},
        )
        token = reg.json()["access_token"]
        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["phone"] == "13800138003"

    def test_get_me_without_token(self, client, clean_db):
        """无 token 访问 /auth/me 返回 401。"""
        resp = client.get("/auth/me")

        assert resp.status_code == 401


class TestAuthUpdateMe:
    """测试更新用户信息接口。"""

    def test_update_nickname(self, client, clean_db):
        """PUT /auth/me 更新昵称成功。"""
        reg = client.post(
            "/auth/register",
            json={"phone": "13800138004", "password": "password123"},
        )
        token = reg.json()["access_token"]
        resp = client.put(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"nickname": "新昵称"},
        )

        assert resp.status_code == 200
        assert resp.json()["nickname"] == "新昵称"

    def test_update_me_without_token(self, client, clean_db):
        """无 token 更新 /auth/me 返回 401。"""
        resp = client.put(
            "/auth/me",
            json={"nickname": "新昵称"},
        )

        assert resp.status_code == 401
