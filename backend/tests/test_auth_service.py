"""Auth service 测试 — 注册、登录、token 校验。"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.services.auth_service import get_user_by_id, login, register


def test_register_success(db_session):
    """正常注册成功，返回 user 和 token。"""
    user, token = register(
        db_session, phone="13800138000", password="pass1234", nickname="张三"
    )
    assert user.phone == "13800138000"
    assert user.nickname == "张三"
    assert user.role == "user"
    assert token is not None
    assert len(token) > 20


def test_register_duplicate_phone(db_session):
    """重复手机号注册失败。"""
    register(db_session, phone="13800138001", password="pass1234")
    with pytest.raises(IntegrityError):
        register(db_session, phone="13800138001", password="pass5678")


def test_login_success(db_session):
    """注册后可以登录，返回 token。"""
    register(db_session, phone="13800138002", password="mypassword")
    user, token = login(db_session, phone="13800138002", password="mypassword")
    assert user is not None
    assert token is not None


def test_login_wrong_password(db_session):
    """密码错误返回 None。"""
    register(db_session, phone="13800138003", password="correct")
    result = login(db_session, phone="13800138003", password="wrong")
    assert result is None


def test_login_nonexistent_phone(db_session):
    """手机号不存在返回 None。"""
    result = login(db_session, phone="99999999999", password="whatever")
    assert result is None


def test_get_user_by_id(db_session):
    """通过 ID 查询用户。"""
    user, _ = register(db_session, phone="13800138004", password="pass")
    found = get_user_by_id(db_session, user.id)
    assert found is not None
    assert found.phone == "13800138004"
