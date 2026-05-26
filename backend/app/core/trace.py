"""Agent 调用链路追踪写入模块。"""

import logging
from typing import Optional

from app.core.database import SessionLocal
from app.models.agent_trace import AgentTrace

logger = logging.getLogger(__name__)

MAX_SUMMARY_LEN = 500

__all__ = ["write_trace"]


def _truncate(text: Optional[str], max_len: int) -> Optional[str]:
    """截断文本到指定长度。"""
    if text is None:
        return None
    return text[:max_len] if len(text) > max_len else text


def write_trace(
    *,
    farm_id: int,
    session_id: Optional[str],
    node_type: str,
    node_name: str,
    input_summary: Optional[str] = None,
    output_summary: Optional[str] = None,
    duration_ms: Optional[int] = None,
    tokens_used: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    """写入一条 Agent 调用追踪记录。异常时仅记录日志，不影响主流程。"""
    db = SessionLocal()
    try:
        trace = AgentTrace(
            farm_id=farm_id,
            session_id=session_id,
            node_type=node_type,
            node_name=node_name,
            input_summary=_truncate(input_summary, MAX_SUMMARY_LEN),
            output_summary=_truncate(output_summary, MAX_SUMMARY_LEN),
            duration_ms=duration_ms,
            tokens_used=tokens_used,
            error_message=error_message,
        )
        db.add(trace)
        db.commit()
    except Exception:
        logger.exception("写入 trace 失败: farm_id=%s, node=%s", farm_id, node_name)
    finally:
        db.close()
