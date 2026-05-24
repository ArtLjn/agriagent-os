"""统一日志模块，提供结构化日志输出。"""

import logging
import sys
import time
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestFormatter(logging.Formatter):
    """带 request_id 的日志格式器。"""

    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get("-")
        return super().format(record)


def setup_logging() -> None:
    """初始化全局日志配置。"""
    fmt = "\033[90m%(asctime)s\033[0m │ %(request_id)s │ %(name)s │ %(levelname)s │ %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_RequestFormatter(fmt))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

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
