"""统一日志模块，提供结构化日志输出（stdout + 文件）。"""

import logging
import os
import sys
import time
from contextvars import ContextVar
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestFormatter(logging.Formatter):
    """带 request_id 的日志格式器。"""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get("-")
        return super().format(record)


def _ensure_log_dir(log_dir: Path) -> Path:
    """确保日志目录存在并返回路径。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def setup_logging() -> None:
    """初始化全局日志配置。

    同时输出到 stdout（带颜色）和文件（纯文本，按天自动轮转）。
    日志目录可通过环境变量 ``LOG_DIR`` 自定义，默认 ``backend/logs/``。
    """
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

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
    for noisy in ("httpx", "httpcore", "urllib3", "openai._base_client", "werkzeug"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """获取命名 logger。"""
    return logging.getLogger(name)


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
