"""MCP 中间件错误响应的统一 JSON 字段测试。"""

from __future__ import annotations

import json

from business.mcp_auth import _error_body


def test_mcp_auth_error_body_contains_stable_code() -> None:
    payload = json.loads(_error_body("mcp_auth_failed", "凭证无效"))

    assert payload == {
        "error": "mcp_auth_failed",
        "code": "mcp_auth_failed",
        "message": "凭证无效",
    }
