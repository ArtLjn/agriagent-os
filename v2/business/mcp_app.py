"""Shared FastMCP instance.

Tools in business/tools/* import `mcp` from here and decorate with @mcp.tool
to register on the same server instance.

模块名刻意叫 mcp_app 而不是 mcp，避免影子化官方 `mcp` 包
（`import mcp.types` 会优先解析到本地 mcp.py，导致 fastmcp 启动失败）。
"""
from fastmcp import FastMCP

# Single FastMCP instance shared across all tool modules.
# Streamable HTTP transport is configured in server.py:main().
mcp: FastMCP = FastMCP("farm-manager-business")
