"""MCP 工具共享的 HTTP 请求头解析工具。

agent 的 BusinessClient 在构造时注入 X-Farm-Id / X-User-Id / X-Agent-Token，
business 侧 MCP tool 通过 get_http_request() 读取这些 headers。
"""
from __future__ import annotations

import logging

from business.config import settings

logger = logging.getLogger(__name__)


def get_farm_id_from_headers() -> int:
    """从当前 MCP HTTP 请求的 X-Farm-Id header 提取农场 ID。

    无 header 或解析失败时回退到 settings.default_farm_id（开发模式兼容）。
    """
    try:
        from fastmcp.server.dependencies import get_http_request

        request = get_http_request()
        raw = request.headers.get("x-farm-id")
        if raw:
            return int(raw)
    except Exception:
        pass
    return settings.default_farm_id


def get_user_id_from_headers() -> str:
    """从 X-User-Id header 提取用户 ID。"""
    try:
        from fastmcp.server.dependencies import get_http_request

        request = get_http_request()
        return request.headers.get("x-user-id", "")
    except Exception:
        return ""
