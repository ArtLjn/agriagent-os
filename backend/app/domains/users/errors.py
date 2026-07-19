"""Auth 稳定错误码与 HTTP 异常辅助。"""

from fastapi import HTTPException

AUTH_MISSING_TOKEN = "AUTH_MISSING_TOKEN"
AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
AUTH_EXPIRED_TOKEN = "AUTH_EXPIRED_TOKEN"
AUTH_USER_NOT_FOUND = "AUTH_USER_NOT_FOUND"
AUTH_USER_DISABLED = "AUTH_USER_DISABLED"
AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
AUTH_ADMIN_REQUIRED = "AUTH_ADMIN_REQUIRED"
AUTH_REGISTER_FAILED = "AUTH_REGISTER_FAILED"


def auth_error(status_code: int, code: str, detail: str) -> HTTPException:
    """构建包含稳定 code 的 Auth HTTP 异常。"""
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "detail": detail},
    )


def missing_token_error() -> HTTPException:
    """未提供 token。"""
    return auth_error(401, AUTH_MISSING_TOKEN, "未提供认证信息")


def invalid_token_error() -> HTTPException:
    """token 无效或已过期。"""
    return auth_error(401, AUTH_INVALID_TOKEN, "token 无效或已过期")


def expired_token_error() -> HTTPException:
    """token 已过期。"""
    return auth_error(401, AUTH_EXPIRED_TOKEN, "token 已过期")


def user_not_found_error() -> HTTPException:
    """token 对应用户不存在。"""
    return auth_error(401, AUTH_USER_NOT_FOUND, "用户不存在")


def user_disabled_error() -> HTTPException:
    """用户已被禁用。"""
    return auth_error(401, AUTH_USER_DISABLED, "用户已被禁用")


def invalid_credentials_error() -> HTTPException:
    """登录凭证错误。"""
    return auth_error(401, AUTH_INVALID_CREDENTIALS, "手机号或密码错误")


def admin_required_error() -> HTTPException:
    """管理员权限不足。"""
    return auth_error(403, AUTH_ADMIN_REQUIRED, "需要管理员权限")


def register_failed_error() -> HTTPException:
    """注册失败。"""
    return auth_error(400, AUTH_REGISTER_FAILED, "该手机号已注册")
