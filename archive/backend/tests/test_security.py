"""安全模块测试 — JWT + bcrypt。"""

from app.domains.users.password import hash_password, verify_password
from app.domains.users.tokens import create_access_token, verify_token


def test_hash_and_verify_password():
    """密码哈希后可以验证。"""
    hashed = hash_password("mypassword123")
    assert hashed != "mypassword123"
    assert verify_password("mypassword123", hashed) is True
    assert verify_password("wrongpassword", hashed) is False


def test_create_and_verify_token():
    """JWT token 签发后可以正确解析出 user_id。"""
    token = create_access_token(user_id="abc-123")
    payload = verify_token(token)
    assert payload["sub"] == "abc-123"
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload


def test_verify_invalid_token_returns_none():
    """无效 token 返回 None。"""
    result = verify_token("invalid.token.value")
    assert result is None


def test_verify_expired_token_returns_none():
    """过期 token 返回 None。"""
    token = create_access_token(user_id="abc-123", expires_minutes=-1)
    result = verify_token(token)
    assert result is None
