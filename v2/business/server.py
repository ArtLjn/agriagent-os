"""MCP Server entry point.

Exposes farm business capabilities as MCP tools over Streamable HTTP.
Agent (separate process) connects via http://127.0.0.1:9876/mcp.

Run: python -m business.server
"""
import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from fastmcp import FastMCP

# Import tool registration side-effects (each module decorates @mcp.tool).
from business.tools import farm, location, logs, weather  # noqa: F401
from business.db import check_connection
from business.mcp_app import mcp


def setup_logging() -> None:
    """初始化 business 进程的日志配置（与 agent 风格一致）。

    Business 进程无 trace 上下文（contextvars 在不同进程），
    所以日志里 request_id/conversation_id/turn_id 字段显示为 "-"。
    """
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    # stdout（彩色，与 agent 一致）
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

    # 文件（按天轮转）
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

    # 第三方库降噪
    for noisy in ("httpx", "httpcore", "urllib3", "watchfiles", "pymongo"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> None:
    setup_logging()
    logger = logging.getLogger(__name__)
    # 启动前确认 MySQL 连通（失败立即崩，避免上线后才发现连接串错）。
    check_connection()
    logger.info("starting MCP server on http://127.0.0.1:9876/mcp")
    # Streamable HTTP transport (SSE is deprecated in MCP spec).
    mcp.run(transport="http", host="127.0.0.1", port=9876, path="/mcp")


if __name__ == "__main__":
    main()
