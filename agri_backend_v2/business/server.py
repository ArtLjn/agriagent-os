"""Business HTTP + MCP server entry point.

Exposes farm business capabilities as MCP tools over Streamable HTTP.
Agent (separate process) connects via http://127.0.0.1:9876/mcp.

REST API 由 FastAPI 提供，FastMCP ASGI 应用挂载在同一进程的 /mcp。

Run: uv run --package farm-manager-business python -m business.server
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from starlette.middleware import Middleware

# Import tool registration side-effects (each module decorates @mcp.tool).
from business.tools import farm, location, logs, user_settings, weather  # noqa: F401
from business.tools import (  # noqa: F401
    cost,
    crop_cycle,
    crop_templates,
    debt,
    planting_plan,
    planting_units,
    work_orders,
    workers,
)
from business.api import api_router, install_exception_handlers
from business.db import check_connection
from business.mcp_app import mcp
from business.mcp_auth import McpAuthMiddleware
from business.services.auth_service import ensure_admin_user


def setup_logging() -> None:
    """初始化 business 进程的日志配置（与 agent 风格一致）。"""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    console_fmt = (
        "\033[90m%(asctime)s\033[0m"
        " │ \033[36m-\033[0m"
        " │ %(name)s"
        " │ %(levelname)s"
        " │ %(message)s"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(console_fmt))
    root.addHandler(console_handler)

    default_log_dir = Path(__file__).resolve().parent.parent / "logs" / "business"
    log_dir = Path(os.getenv("LOG_DIR", default_log_dir))
    log_dir.mkdir(parents=True, exist_ok=True)

    file_fmt = "%(asctime)s │ - │ - │ - │ %(name)s │ %(levelname)s │ %(message)s"
    app_handler = TimedRotatingFileHandler(
        log_dir / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    app_handler.setFormatter(logging.Formatter(file_fmt))
    root.addHandler(app_handler)

    error_handler = TimedRotatingFileHandler(
        log_dir / "error.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    error_handler.setFormatter(logging.Formatter(file_fmt))
    error_handler.setLevel(logging.WARNING)
    root.addHandler(error_handler)

    for noisy in ("httpx", "httpcore", "urllib3", "watchfiles", "pymongo"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def create_app() -> FastAPI:
    """创建同时承载 REST 与 MCP 的 ASGI 应用。"""
    mcp_app = mcp.http_app(path="/mcp", middleware=[Middleware(McpAuthMiddleware)])
    app = FastAPI(
        title="Farm Manager Business API",
        version="2.0.0",
        lifespan=mcp_app.lifespan,
    )
    install_exception_handlers(app)
    app.include_router(api_router)
    # 挂在根路径可保留标准 /mcp，不触发 Starlette 对 /mcp/ 的重定向。
    app.mount("/", mcp_app)
    return app


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    check_connection()
    ensure_admin_user()
    logger.info("starting business server on http://127.0.0.1:9876")
    logger.info("REST API: http://127.0.0.1:9876/api/v2")
    logger.info("MCP endpoint: http://127.0.0.1:9876/mcp")
    uvicorn.run(create_app(), host="127.0.0.1", port=9876, ws="auto")


if __name__ == "__main__":
    main()
