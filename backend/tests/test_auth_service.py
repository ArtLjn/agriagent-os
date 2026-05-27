"""Auth service 测试 — 注册、登录、token 校验。"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.services.auth_service import register, login, get_user_by_id


def test_register_success():
    """正常注册成功，返回 user 和 token。"""
    db = SessionLocal()
    try:
        user, token = register(
            db, phone="13800138000", password="pass1234", nickname="张三"
        )
        assert user.phone == "13800138000"
        assert user.nickname == "张三"
        assert user.role == "user"
        assert token is not None
        assert len(token) > 20
    finally:
        db.close()


def test_register_duplicate_phone():
    """重复手机号注册失败。"""
    db = SessionLocal()
    try:
        register(db, phone="13800138001", password="pass1234")
        with pytest.raises(IntegrityError):
            register(db, phone="13800138001", password="pass5678")
    finally:
        db.close()


def test_login_success():
    """注册后可以登录，返回 token。"""
    db = SessionLocal()
    try:
        register(db, phone="13800138002", password="mypassword")
        user, token = login(db, phone="13800138002", password="mypassword")
        assert user is not None
        assert token is not None
    finally:
        db.close()


def test_login_wrong_password():
    """密码错误返回 None。"""
    db = SessionLocal()
    try:
        register(db, phone="13800138003", password="correct")
        result = login(db, phone="13800138003", password="wrong")
        assert result is None
    finally:
        db.close()


def test_login_nonexistent_phone():
    """手机号不存在返回 None。"""
    db = SessionLocal()
    try:
        result = login(db, phone="99999999999", password="whatever")
        assert result is None
    finally:
        db.close()


def test_get_user_by_id():
    """通过 ID 查询用户。"""
    db = SessionLocal()
    try:
        user, _ = register(db, phone="13800138004", password="pass")
        found = get_user_by_id(db, user.id)
        assert found is not None
        assert found.phone == "13800138004"
    finally:
        db.close()
