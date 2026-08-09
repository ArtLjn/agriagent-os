"""MCP Client wrapper for business server.

Connects to business MCP Server at http://127.0.0.1:9876/mcp via
Streamable HTTP. Provides:
  - list_tools()      : discover available tools + descriptions
  - call_tool(name, args) : invoke a tool, return structured dict
  - close()           : shutdown client session

Designed to be invoked from agent react loop. The connection is
session-scoped (one client per ReAct turn) to avoid shared state issues.

身份注入：构造时传入 headers（X-Farm-Id / X-User-Id / X-Agent-Token），
business MCP tools 通过 get_http_request() 读取这些 headers 做农场隔离。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

import httpx
from fastmcp import Client
from fastmcp.client.transports.http import StreamableHttpTransport

logger = logging.getLogger(__name__)

# Business server URL — configurable via env for docker / remote setups.
BUSINESS_MCP_URL = os.environ.get("BUSINESS_MCP_URL")


def _configured_business_mcp_url() -> str:
    """按环境变量、Agent 配置文件顺序解析 Business MCP 地址。"""
    if BUSINESS_MCP_URL:
        return BUSINESS_MCP_URL
    from agent.config import settings

    return settings.business_mcp.url


def _is_loopback_url(url: str) -> bool:
    """本地 Business 服务不应被系统代理接管。"""
    hostname = (urlparse(url).hostname or "").lower()
    return hostname in {"127.0.0.1", "localhost", "::1"}


def _local_httpx_factory() -> Callable[..., httpx.AsyncClient]:
    """构造绕过环境代理的 HTTPX client factory。"""

    def factory(
        *,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | None = None,
        follow_redirects: bool = True,
        timeout: httpx.Timeout | None = None,
        **_: Any,
    ) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=headers,
            auth=auth,
            follow_redirects=follow_redirects,
            timeout=timeout,
            trust_env=False,
        )

    return factory


class BusinessClient:
    """Thin wrapper around fastmcp.Client for the business server.

    Use as async context manager:
        async with BusinessClient(headers={"X-Farm-Id": "1"}) as client:
            tools = await client.list_tools()
            result = await client.call_tool("get_farm_status", {})

    Args:
        url: MCP server endpoint.
        headers: 身份 headers，注入到每个 MCP HTTP 请求。
                 业务侧通过 get_http_request().headers 读取。
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url or _configured_business_mcp_url()
        self._headers = headers or {}
        self._client: Client | None = None

    async def __aenter__(self) -> "BusinessClient":
        logger.info("connecting to business MCP server: %s", self.url)
        transport_kwargs: dict[str, Any] = {"headers": self._headers}
        if _is_loopback_url(self.url):
            transport_kwargs["httpx_client_factory"] = _local_httpx_factory()
            logger.debug("bypassing environment proxy for loopback Business MCP")
        transport = StreamableHttpTransport(self.url, **transport_kwargs)
        self._client = Client(transport)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._client is not None:
            await self._client.__aexit__(exc_type, exc, tb)
            self._client = None

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return [{name, description, input_schema}] for all business tools."""
        if self._client is None:
            raise RuntimeError("BusinessClient not entered")
        result = await self._client.list_tools()
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.inputSchema or {},
            }
            for t in result
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Invoke a business tool. Returns its structured data dict.

        Raises ValueError if business returns an error payload,
        RuntimeError if client not entered.
        """
        if self._client is None:
            raise RuntimeError("BusinessClient not entered")
        logger.info("calling business tool: %s args=%s", name, arguments)
        result = await self._client.call_tool(name, arguments)
        # FastMCP returns CallToolResult with .data (structured) and .content
        # (text fallback). We use structured data when available.
        if hasattr(result, "data") and result.data is not None:
            return result.data
        # Fallback: aggregate text content.
        texts = []
        for c in result.content or []:
            texts.append(getattr(c, "text", str(c)))
        return {"_text": "\n".join(texts)}
