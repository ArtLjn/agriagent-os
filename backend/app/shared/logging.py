"""统一日志模块，提供结构化日志输出（stdout + 文件）。"""

import json
import logging
import os
import sys
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

_STRUCTURED_ATTR = "structured_log"
_SENSITIVE_LOG_KEYS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}


class _RequestFormatter(logging.Formatter):
    """带 request_id 的日志格式器。"""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get("-")
        return super().format(record)


class JsonLineFormatter(logging.Formatter):
    """输出单行 JSON 结构化日志。"""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": _format_record_time(record),
            "level": record.levelname,
            "logger": record.name,
            "message": _single_line(record.getMessage()),
            "request_id": request_id_var.get("-"),
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
    trace_id: str | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    turn_id: str | None = None,
    step_id: str | None = None,
    status: str | None = None,
    duration_ms: int | None = None,
    labels: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> None:
    """记录稳定字段的结构化事件日志。"""
    structured = _structured_payload(
        event=event,
        code=code,
        trace_id=trace_id,
        request_id=request_id,
        session_id=session_id,
        turn_id=turn_id,
        step_id=step_id,
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


def _ensure_log_dir(log_dir: Path) -> Path:
    """确保日志目录存在并返回路径。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _reenable_project_loggers() -> None:
    """恢复被 Alembic fileConfig 禁用的项目 logger。"""
    manager = logging.root.manager
    for name, logger_obj in manager.loggerDict.items():
        if not name.startswith("app."):
            continue
        if isinstance(logger_obj, logging.Logger):
            logger_obj.disabled = False
            logger_obj.propagate = True


def setup_logging() -> None:
    """初始化全局日志配置。

    同时输出到 stdout（带颜色）和文件（纯文本，按天自动轮转）。
    日志目录可通过环境变量 ``LOG_DIR`` 自定义，默认 ``backend/logs/``。
    """
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)
    _reenable_project_loggers()

    # ── 1. stdout 处理器（带颜色）─
    console_fmt = (
        "\033[90m%(asctime)s\033[0m"
        " │ %(request_id)s │ %(name)s │ %(levelname)s │ %(message)s"
    )
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_RequestFormatter(console_fmt))
    root.addHandler(console_handler)

    # ── 2. 文件处理器（纯文本，轮转）─
    log_dir = _ensure_log_dir(
        Path(os.getenv("LOG_DIR", Path(__file__).resolve().parent.parent / "logs"))
    )
    file_fmt = "%(asctime)s │ %(request_id)s │ %(name)s │ %(levelname)s │ %(message)s"

    # 2a. 全量日志 app.log（INFO 及以上），每天零点自动轮转
    app_handler = TimedRotatingFileHandler(
        log_dir / "app.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    app_handler.setFormatter(logging.Formatter(file_fmt))
    root.addHandler(app_handler)

    if os.getenv("LOG_JSONL", "").lower() in {"1", "true", "yes"}:
        json_handler = TimedRotatingFileHandler(
            log_dir / "app.jsonl",
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        json_handler.setFormatter(JsonLineFormatter())
        root.addHandler(json_handler)

    # 2b. 错误日志 error.log（WARNING 及以上），每天零点自动轮转
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
    for noisy in (
        "httpx",
        "httpcore",
        "urllib3",
        "openai._base_client",
        "werkzeug",
        "watchfiles",
        "watchfiles.main",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取命名 logger。"""
    return logging.getLogger(name)


def _structured_payload(
    *,
    event: str,
    code: str | None,
    trace_id: str | None,
    request_id: str | None,
    session_id: str | None,
    turn_id: str | None,
    step_id: str | None,
    status: str | None,
    duration_ms: int | None,
    labels: dict[str, Any] | None,
    data: dict[str, Any] | None,
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"event": event}
    for key, value in (
        ("code", code),
        ("trace_id", trace_id),
        ("request_id", request_id),
        ("session_id", session_id),
        ("turn_id", turn_id),
        ("step_id", step_id),
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
    flat_items: list[tuple[str, Any]] = []
    for key, value in payload.items():
        if key == "data" and isinstance(value, dict):
            flat_items.extend(
                (item_key, item_value) for item_key, item_value in value.items()
            )
            continue
        if key in {"labels", "error"}:
            continue
        flat_items.append((key, value))
    return " ".join(
        f"{key}={_format_key_value(value)}"
        for key, value in flat_items
        if value is not None
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
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if _is_sensitive_log_key(key)
            else _sanitize_log_value(item)
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
    return " ".join(value.splitlines())


def _format_record_time(record: logging.LogRecord) -> str:
    return datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()


class Timer:
    """简单的计时上下文管理器。"""

    def __init__(self, logger: logging.Logger, label: str):
        self._logger = logger
        self._label = label
        self._start = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_):
        elapsed = time.perf_counter() - self._start
        self._logger.info("%s 耗时 %.2fs", self._label, elapsed)
