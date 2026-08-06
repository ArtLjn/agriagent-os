"""统一日志模块 — 结构化输出 + trace 上下文注入。

参考 archive/backend/app/shared/logging.py，适配 v2 架构：
- 接入 agent.infra.trace.context 的 TraceInfo（request_id/conversation_id/turn_id）
- 三路输出：
  1. stdout（彩色，开发友好）
  2. logs/app.log（纯文本，按天轮转）
  3. logs/app.jsonl（结构化 JSON，便于 ELK/Loki 采集，需设 LOG_JSONL=1）
- logs/error.log 单独存放 WARNING 及以上
- 第三方库降噪（httpx/openai/watchfiles 等）

用法：
    from agent.infra.logging import setup_logging, get_logger, log_event
    setup_logging()  # 进程启动时调用一次
    logger = get_logger(__name__)
    logger.info("hello %s", name)
    log_event(logger, logging.INFO, "llm_call", turn_id=..., duration_ms=...)
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

# 标记 LogRecord.extra 里的结构化字段，JsonLineFormatter 会读取它并合并到 JSON 输出。
_STRUCTURED_ATTR = "structured_log"
# 敏感字段名（小写匹配），打到日志里会被替换为 [REDACTED]。
_SENSITIVE_LOG_KEYS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "uri",  # MongoDB/MySQL 连接串含密码
}
# 正则：匹配 mongodb://user:password@host 或 mysql://user:password@host 的密码段
# 用于脱敏普通字符串日志消息里的连接串。
_CREDENTIAL_IN_URI_PATTERN = re.compile(
    r"(://[^:/@\s]+:)([^@\s]+)(@)",
    flags=re.IGNORECASE,
)


def _redact_uri_credentials(message: str) -> str:
    """脱敏 URL 里的密码段：mongodb://user:pass@host → mongodb://user:***@host。"""
    return _CREDENTIAL_IN_URI_PATTERN.sub(r"\1***\3", message)


def _get_trace_fields() -> dict[str, str]:
    """从 contextvars 取 trace 字段，注入到每条日志。

    没有 trace 上下文（如启动阶段、非请求线程）时返回空 dict。
    """
    try:
        from agent.infra.trace.context import get_trace
        trace = get_trace()
        if trace is None:
            return {}
        return {
            "request_id": trace.request_id,
            "conversation_id": trace.conversation_id,
            "turn_id": trace.turn_id,
        }
    except Exception:
        # trace 模块未就绪或循环导入，静默跳过。
        return {}


class _TraceFormatter(logging.Formatter):
    """注入 trace 字段到 LogRecord，供后续 format 字符串引用。"""

    def format(self, record: logging.LogRecord) -> str:
        trace_fields = _get_trace_fields()
        record.request_id = trace_fields.get("request_id", "-")
        record.conversation_id = trace_fields.get("conversation_id", "-")
        record.turn_id = trace_fields.get("turn_id", "-")
        formatted = super().format(record)
        # 脱敏 URL 凭据（mongodb://user:pass@host 等），不修改 record.msg 避免 handler 间污染
        return _redact_uri_credentials(formatted)


class JsonLineFormatter(logging.Formatter):
    """单行 JSON 结构化日志。

    字段：timestamp/level/logger/message/request_id/conversation_id/turn_id
    加上 log_event() 传入的稳定结构化字段。
    """

    def format(self, record: logging.LogRecord) -> str:
        trace_fields = _get_trace_fields()
        payload: dict[str, Any] = {
            "timestamp": _format_record_time(record),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_uri_credentials(_single_line(record.getMessage())),
            "request_id": trace_fields.get("request_id", "-"),
            "conversation_id": trace_fields.get("conversation_id", "-"),
            "turn_id": trace_fields.get("turn_id", "-"),
        }
        structured = getattr(record, _STRUCTURED_ATTR, None)
        if isinstance(structured, dict):
            payload.update(structured)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(_sanitize_log_value(payload), ensure_ascii=False)


def log_event(
    logger: logging.Logger,
    level: int,
    event: str,
    *,
    code: str | None = None,
    status: str | None = None,
    duration_ms: int | None = None,
    labels: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    """记录稳定字段的结构化事件日志。

    在 JSON 输出里会展开为 {event, code, status, duration_ms, ...}。
    在 stdout/纯文本输出里会拼成 key=value 形式追加到 message 后。
    trace 字段（request_id/conversation_id/turn_id）由 Formatter 自动注入，不用传。
    """
    structured = _structured_payload(
        event=event,
        code=code,
        status=status,
        duration_ms=duration_ms,
        labels=labels,
        data=data,
        error=error,
    )
    logger.log(
        level,
        _key_value_message(structured),
        extra={_STRUCTURED_ATTR: structured},
    )


def setup_logging(
    *,
    app_name: str = "agent",
    log_dir_env: str = "LOG_DIR",
    jsonl_env: str = "LOG_JSONL",
) -> None:
    """初始化全局日志配置。

    Args:
        app_name: 日志前缀（agent/business），用于日志目录区分
        log_dir_env: 日志目录环境变量名，默认 LOG_DIR
        jsonl_env: 启用 JSON 输出的环境变量名，默认 LOG_JSONL
    """
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    # ── 1. stdout（彩色 + trace 字段）─
    console_fmt = (
        "\033[90m%(asctime)s\033[0m"
        " │ \033[36m%(request_id)s\033[0m"
        " │ %(name)s"
        " │ %(levelname)s"
        " │ %(message)s"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_TraceFormatter(console_fmt))
    root.addHandler(console_handler)

    # ── 2. 文件（按天轮转）─
    default_log_dir = Path(__file__).resolve().parent.parent.parent / "logs" / app_name
    log_dir = Path(os.getenv(log_dir_env, default_log_dir))
    log_dir.mkdir(parents=True, exist_ok=True)

    file_fmt = (
        "%(asctime)s │ %(request_id)s │ %(conversation_id)s │ %(turn_id)s"
        " │ %(name)s │ %(levelname)s │ %(message)s"
    )

    # 2a. 全量 app.log
    app_handler = TimedRotatingFileHandler(
        log_dir / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    app_handler.setFormatter(_TraceFormatter(file_fmt))
    root.addHandler(app_handler)

    # 2b. 错误 error.log（WARNING 及以上）
    error_handler = TimedRotatingFileHandler(
        log_dir / "error.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    error_handler.setFormatter(_TraceFormatter(file_fmt))
    error_handler.setLevel(logging.WARNING)
    root.addHandler(error_handler)

    # 2c. 结构化 JSON（可选，LOG_JSONL=1 启用）
    if os.getenv(jsonl_env, "").lower() in {"1", "true", "yes"}:
        json_handler = TimedRotatingFileHandler(
            log_dir / "app.jsonl",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        json_handler.setFormatter(JsonLineFormatter())
        root.addHandler(json_handler)

    # 第三方库降噪
    for noisy in (
        "httpx",
        "httpcore",
        "urllib3",
        "openai._base_client",
        "watchfiles",
        "watchfiles.main",
        "pymongo",
        "motor",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取命名 logger。"""
    return logging.getLogger(name)


# ─────────────────────────────────────────────────────────────
# 内部工具函数
# ─────────────────────────────────────────────────────────────


def _structured_payload(
    *,
    event: str,
    code: str | None,
    status: str | None,
    duration_ms: int | None,
    labels: dict[str, Any] | None,
    data: dict[str, Any] | None,
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"event": event}
    for key, value in (
        ("code", code),
        ("status", status),
        ("duration_ms", duration_ms),
        ("labels", labels),
        ("data", data),
        ("error", error),
    ):
        if value is not None:
            payload[key] = _sanitize_log_value(value)
    return payload


def _key_value_message(payload: dict[str, Any]) -> str:
    """把结构化字段拼成 key=value 文本，追加到日志消息后。

    JSON 输出会保留完整结构化字段；stdout/纯文本输出只看到这个拼接消息。
    """
    flat_items: list[tuple[str, Any]] = []
    for key, value in payload.items():
        if key == "data" and isinstance(value, dict):
            flat_items.extend(value.items())
            continue
        if key in {"labels", "error"}:
            continue
        flat_items.append((key, value))
    return " ".join(
        f"{k}={_format_key_value(v)}" for k, v in flat_items if v is not None
    )


def _format_key_value(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(_single_line(str(item)) for item in value)
    if isinstance(value, dict):
        return _single_line(
            json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        )
    return _single_line(str(value))


def _sanitize_log_value(value: Any) -> Any:
    """递归脱敏：dict 里 key 命中 _SENSITIVE_LOG_KEYS 的值替换为 [REDACTED]。"""
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if _is_sensitive_log_key(key) else _sanitize_log_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_log_value(item) for item in value]
    if isinstance(value, str):
        return _single_line(value)
    return value


def _is_sensitive_log_key(key: Any) -> bool:
    return str(key).strip().lower() in _SENSITIVE_LOG_KEYS


def _single_line(value: str) -> str:
    """把多行字符串压成一行，避免 JSON 日志被换行截断。"""
    return " ".join(value.splitlines())


def _format_record_time(record: logging.LogRecord) -> str:
    return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()


__all__ = [
    "setup_logging",
    "get_logger",
    "log_event",
    "JsonLineFormatter",
]
