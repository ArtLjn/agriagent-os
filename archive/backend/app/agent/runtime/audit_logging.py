"""Agent Runtime 审计日志辅助函数。"""

import logging
from typing import Any

from app.shared.logging import log_event

logger = logging.getLogger("app.agent.audit")


def log_agent_audit(
    *,
    phase: str,
    boundary: str,
    sop: str,
    status: str,
    duration_ms: int | None = None,
    **data: Any,
) -> None:
    """记录单行 Agent 审计日志，只接收摘要字段。"""
    safe_data = {
        "phase": phase,
        "boundary": boundary,
        "sop": sop,
        **{key: value for key, value in data.items() if value is not None},
    }
    log_event(
        logger,
        logging.INFO,
        "agent_audit",
        status=status,
        duration_ms=duration_ms,
        data=safe_data,
    )
