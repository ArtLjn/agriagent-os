"""流式聊天尾部事件和完成日志。"""

import logging
import time
from collections.abc import AsyncGenerator

from app.agent.application.stream_chat_types import (
    ResponseEvent,
    StreamMetadata,
    StreamReplyState,
    format_sse_event,
)
from app.models.conversation import Conversation

logger = logging.getLogger(__name__)


async def yield_metadata_events(
    request_id: str,
    metadata: StreamMetadata,
) -> AsyncGenerator[str, None]:
    """在正文结束后发送结构化尾事件。"""
    if metadata.skill_names:
        yield format_sse_event(
            ResponseEvent("skills", {"skills": metadata.skill_names})
        )

    if metadata.pending_action:
        logger.info(
            "[%s] 发送 pending_action SSE 事件 | skill=%s",
            request_id,
            metadata.pending_action.skill_name,
        )
        yield format_sse_event(
            ResponseEvent(
                "pending_action",
                {"pending_action": metadata.pending_action.model_dump()},
            )
        )
    if metadata.pending_plan:
        yield format_sse_event(
            ResponseEvent(
                "pending_plan",
                {"pending_plan": metadata.pending_plan.model_dump()},
            )
        )


def log_stream_completed(
    *,
    request_id: str,
    started_at: float,
    reply_state: StreamReplyState,
    metadata: StreamMetadata,
    conversation: Conversation | None,
) -> None:
    logger.info(
        "[%s] /chat/stream 完成 | 耗时 %.2fs | reply %d 字符 | skills=%s conversation=%s",
        request_id,
        time.perf_counter() - started_at,
        len(reply_state.full_reply),
        metadata.skill_names,
        conversation.id if conversation else None,
    )
