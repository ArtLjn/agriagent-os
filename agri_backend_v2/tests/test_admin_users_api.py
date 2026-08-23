"""管理员用户管理 REST 路由的权限和注册复用合同测试。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from business.api import users
from business.api.deps import get_current_admin


def test普通用户不能访问管理员资源() -> None:
    """管理员资源必须在通用用户认证之后再次校验角色。"""
    with pytest.raises(HTTPException) as raised:
        get_current_admin({"user_id": "user-1", "role": "user"})

    assert raised.value.status_code == 403
    assert raised.value.detail["code"] == "admin_required"


def test管理员列表透传分页和筛选参数(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}

    def fake_list_users(**kwargs: object) -> dict:
        captured.update(kwargs)
        return {"items": [], "total": 0}

    monkeypatch.setattr(users.user_service, "list_users", fake_list_users)

    result = users.list_admin_users(
        page=2,
        page_size=30,
        status_filter="active",
        role="user",
        phone_keyword="188",
        _admin={"role": "admin"},
    )

    assert result == {"items": [], "total": 0}
    assert captured == {
        "page": 2,
        "size": 30,
        "status": "active",
        "role": "user",
        "keyword": "188",
    }


def test管理员创建复用注册服务且不返回新用户令牌(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created_user = SimpleNamespace(id="user-2")
    calls: dict = {}

    def fake_register(phone: str, password: str, nickname: str, *, role):
        calls.update(
            phone=phone,
            password=password,
            nickname=nickname,
            role=role.value,
        )
        return created_user, "new-user-token"

    monkeypatch.setattr(users.auth_service, "register", fake_register)
    monkeypatch.setattr(
        users.user_service,
        "get_admin_user_detail",
        lambda user_id: {
            "id": user_id,
            "phone": "18812345678",
            "nickname": "新农友",
            "role": "user",
            "status": "active",
            "farm_name": "新农友的农场",
        },
    )

    result = users.create_admin_user(
        users.AdminCreateUserRequest(
            phone="18812345678",
            password="password123",
            nickname="新农友",
        ),
        _admin={"role": "admin"},
    )

    assert calls == {
        "phone": "18812345678",
        "password": "password123",
        "nickname": "新农友",
        "role": "user",
    }
    assert result["id"] == "user-2"
    assert "access_token" not in result
