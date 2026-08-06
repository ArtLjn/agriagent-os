"""MCP Client wrapper for business server.

Connects to business MCP Server at http://127.0.0.1:9876/mcp via
Streamable HTTP. Provides:
  - list_tools()      : discover available tools + descriptions
  - call_tool(name, args) : invoke a tool, return structured dict
  - close()           : shutdown client session

Designed to be invoked from agent react loop. The connection is
session-scoped (one client per ReAct turn) to avoid shared state issues.
"""
from __future__ import annotations

import logging
from typing import Any

from fastmcp import Client

logger = logging.getLogger(__name__)

# Business server URL — configurable via env for docker / remote setups.
import os

BUSINESS_MCP_URL = os.environ.get(
    "BUSINESS_MCP_URL", "http://127.0.0.1:9876/mcp"
)


class BusinessClient:
    """Thin wrapper around fastmcp.Client for the business server.

    Use as async context manager:
        async with BusinessClient() as client:
            tools = await client.list_tools()
            result = await client.call_tool("get_farm_status", {})
    """

    def __init__(self, url: str = BUSINESS_MCP_URL) -> None:
        self.url = url
        self._client: Client | None = None

    async def __aenter__(self) -> "BusinessClient":
        logger.info("connecting to business MCP server: %s", self.url)
        self._client = Client(self.url)
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

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
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
        for c in (result.content or []):
            texts.append(getattr(c, "text", str(c)))
        return {"_text": "\n".join(texts)}
