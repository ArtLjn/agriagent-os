"""MCP 工具共享的已验证身份读取工具。"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def get_farm_id_from_headers() -> int:
    """从 MCP 鉴权 middleware 注入的 Principal 读取内部 farm_id。"""
    return get_principal()["farm_id"]


def get_user_id_from_headers() -> str:
    """从 MCP 鉴权 middleware 注入的 Principal 读取用户 ID。"""
    return get_principal()["user_id"]


def get_principal() -> dict:
    """读取已验证 Principal；缺失时 fail closed。"""
    from fastmcp.server.dependencies import get_http_request

    request = get_http_request()
    principal = getattr(request.state, "principal", None)
    if not principal:
        raise RuntimeError("MCP request principal missing")
    return principal
