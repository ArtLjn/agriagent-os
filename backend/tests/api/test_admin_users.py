"""Admin 用户管理 API 集成测试。"""

import pytest
from fastapi import Depends

from app.api.deps import get_current_user
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.farm import Farm
from app.models.user import User


@pytest.fixture()
def admin_user():
    """创建管理员用户到数据库并覆盖 get_current_user 返回管理员。"""
    db = SessionLocal()
    admin = User(
        id="test-admin-001",
        phone="99999999999",
        password_hash="h",
        nickname="管理员",
        role="admin",
        status="active",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.close()

    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: admin
    yield admin
    if original:
        app.dependency_overrides[get_current_user] = original
    else:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def admin_headers():
    """管理员 JWT 请求头。"""
    token = create_access_token(user_id="test-admin-001")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def target_user():
    """创建一个用于禁用/启用的目标普通用户。"""
    db = SessionLocal()
    user = User(
        id="test-target-001",
        phone="11111111111",
        password_hash="h",
        nickname="目标用户",
        role="user",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def test_list_users_empty(client, admin_user, admin_headers):
    """管理员查询用户列表。"""
    resp = client.get("/admin/users", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_list_users_filter_by_status(client, admin_user, admin_headers):
    """按状态筛选用户。"""
    resp = client.get("/admin/users?status=active", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all(u["status"] == "active" for u in data["items"])


def test_list_users_search_phone(client, admin_user, admin_headers):
    """按手机号模糊搜索。"""
    resp = client.get("/admin/users?phone_keyword=9999", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any("9999" in u["phone"] for u in data["items"])


def test_list_users_pagination(client, admin_user, admin_headers):
    """分页查询。"""
    resp = client.get("/admin/users?page=1&size=1", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 1


def test_get_user_detail(client, admin_user, admin_headers):
    """获取用户详情。"""
    resp = client.get(f"/admin/users/{admin_user.id}", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == admin_user.id
    assert data["phone"] == "99999999999"
    assert "farm_id" in data
    assert "farm_name" in data


def test_get_user_detail_not_found(client, admin_user, admin_headers):
    """查询不存在的用户。"""
    resp = client.get("/admin/users/nonexistent-id", headers=admin_headers)
    assert resp.status_code == 404


def test_update_user_status_disable(client, admin_user, admin_headers, target_user):
    """禁用用户。"""
    resp = client.put(
        f"/admin/users/{target_user.id}/status",
        json={"status": "disabled"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


def test_update_user_status_enable(client, admin_user, admin_headers, target_user):
    """启用用户。"""
    client.put(
        f"/admin/users/{target_user.id}/status",
        json={"status": "disabled"},
        headers=admin_headers,
    )
    resp = client.put(
        f"/admin/users/{target_user.id}/status",
        json={"status": "active"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


def test_update_admin_status_forbidden(client, admin_user, admin_headers):
    """不能修改管理员状态。"""
    resp = client.put(
        f"/admin/users/{admin_user.id}/status",
        json={"status": "disabled"},
        headers=admin_headers,
    )
    assert resp.status_code == 400


def test_non_admin_forbidden(client, auth_headers):
    """普通用户访问 admin 接口返回 403。"""
    resp = client.get("/admin/users", headers=auth_headers)
    assert resp.status_code == 403


def test_no_auth_returns_401(client):
    """未认证访问返回 401。"""
    original = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides.pop(get_current_user, None)
    try:
        resp = client.get("/admin/users")
        assert resp.status_code == 401
    finally:
        if original:
            app.dependency_overrides[get_current_user] = original
