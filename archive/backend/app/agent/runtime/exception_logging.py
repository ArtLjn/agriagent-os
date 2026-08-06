"""Agent runtime 异常日志工具。"""

import logging


def log_silent_exception(
    logger: logging.Logger,
    *,
    level: int,
    function: str,
    agent_event: str,
    exc: Exception,
) -> None:
    """记录原本会被静默吞掉的异常。"""
    message = str(exc)[:200]
    context = {
        "module": logger.name,
        "function": function,
        "agent_event": agent_event,
        "error_type": exc.__class__.__name__,
        "error_message": message,
    }
    logger.log(
        level,
        "agent silent exception caught",
        extra={
            "agent_context": context,
            "agent_event": agent_event,
            "error_type": exc.__class__.__name__,
            "error_message": message,
            "source_module": logger.name,
            "source_function": function,
        },
        exc_info=True,
    )


__all__ = ["log_silent_exception"]
