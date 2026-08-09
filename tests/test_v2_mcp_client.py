"""Agent 到 Business MCP 的连接回归测试。"""

import asyncio

from agent.infra.mcp_client import _is_loopback_url, _local_httpx_factory


def test_loopback_business_url_is_detected() -> None:
    assert _is_loopback_url("http://127.0.0.1:9876/mcp")
    assert _is_loopback_url("http://localhost:9876/mcp")
    assert _is_loopback_url("http://[::1]:9876/mcp")
    assert not _is_loopback_url("http://business.internal:9876/mcp")


def test_loopback_httpx_factory_bypasses_environment_proxy() -> None:
    client = _local_httpx_factory()(headers={"X-Test": "1"})
    try:
        assert client._trust_env is False
        assert client.headers["X-Test"] == "1"
    finally:
        asyncio.run(client.aclose())
