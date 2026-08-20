"""用户偏好设置 MCP 工具。

用户身份来自 MCP 委托凭证，不接受模型传入 user_id，避免越权读取或修改其他用户的设置。
"""

from __future__ import annotations

from business.mcp_app import mcp
from business.services import user_service
from business.tools._headers import get_user_id_from_headers


def _error(code: str, message: str, **context: object) -> dict:
    result = {
        "error": code,
        "code": code,
        "message": message,
        "retryable": False,
    }
    if context:
        result["context"] = context
    return result


def _validate_update(
    *,
    default_city: str | None,
    default_lat: float | None,
    default_lon: float | None,
    assistant_role: str | None,
) -> dict | None:
    """在 MCP 边界复用 REST 设置接口的约束，避免绕过 HTTP schema。"""
    if all(
        value is None
        for value in (default_city, default_lat, default_lon, assistant_role)
    ):
        return _error(
            "missing_setting_fields",
            "update 操作至少需要提供一个要修改的设置字段",
        )
    if default_city is not None and (
        not default_city.strip() or len(default_city) > 50
    ):
        return _error("invalid_default_city", "default_city 必须是 1-50 个字符")
    if default_lat is not None and not -90 <= default_lat <= 90:
        return _error("invalid_default_lat", "default_lat 必须在 -90 到 90 之间")
    if default_lon is not None and not -180 <= default_lon <= 180:
        return _error("invalid_default_lon", "default_lon 必须在 -180 到 180 之间")
    if assistant_role is not None and assistant_role not in {
        "warm",
        "professional",
        "concise",
    }:
        return _error(
            "invalid_assistant_role",
            "assistant_role 必须是 warm、professional 或 concise",
        )
    return None


@mcp.tool
def manage_user_settings(
    operation: str,
    default_city: str | None = None,
    default_lat: float | None = None,
    default_lon: float | None = None,
    assistant_role: str | None = None,
) -> dict:
    """查询或更新当前登录用户的偏好设置。"""
    user_id = get_user_id_from_headers()
    op = (operation or "").lower()

    if op == "query":
        settings = user_service.get_user_settings(user_id)
        return {
            "user_id": user_id,
            "configured": settings is not None,
            "settings": settings or {},
        }

    if op == "update":
        validation_error = _validate_update(
            default_city=default_city,
            default_lat=default_lat,
            default_lon=default_lon,
            assistant_role=assistant_role,
        )
        if validation_error is not None:
            return validation_error
        updated = user_service.update_user_settings(
            user_id,
            default_city=default_city,
            default_lat=default_lat,
            default_lon=default_lon,
            assistant_role=assistant_role,
        )
        return {"user_id": user_id, "updated": True, "settings": updated}

    return _error(
        "invalid_operation",
        "operation 必须是 query 或 update",
        operation=operation,
    )


__all__ = ["manage_user_settings"]
