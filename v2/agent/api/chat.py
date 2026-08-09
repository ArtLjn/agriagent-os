"""POST /api/v2/chat — SSE ReAct 事件流。"""

from __future__ import annotations

import logging

from fastapi import Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.api import api_router
from agent.auth import parse_identity
from agent.deps import active_turns, approval_waiter, pending_approvals
from agent.core.react import run_turn
from agent.core.turn import Turn
from agent.infra.chat_store import append_message
from agent.infra.sse import sse_event
from agent.infra.trace import clear_trace, flush_now, init_trace, trace_turn_outcome

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


@api_router.post("/chat")
async def chat(
    req: ChatRequest,
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    """Start a ReAct turn and stream events back as SSE."""
    conv_id = req.conversation_id or "default"
    identity = parse_identity(authorization)
    turn = Turn(
        conversation_id=conv_id,
        user_input=req.message,
        user_id=identity["user_id"],
        farm_id=identity["farm_id"],
        agent_token=identity["agent_token"],
    )
    active_turns[turn.turn_id] = turn

    # 落库 user message（不阻塞 stream；失败 infra 内部已降级 warning）
    await append_message(
        conversation_id=conv_id,
        role="user",
        content=req.message,
    )

    async def event_stream():
        final_answer = ""
        init_trace(conversation_id=conv_id, turn_id=turn.turn_id)
        try:
            async for event in run_turn(turn, approval_waiter):
                ev_type = event.get("type", "")
                if ev_type == "final_answer":
                    final_answer = event.get("data", {}).get("text", "")
                elif ev_type == "final_answer_delta":
                    final_answer += event.get("data", {}).get("delta", "")
                yield sse_event(ev_type, event.get("data", {}))
        except Exception as exc:
            logger.exception("event stream crashed")
            yield sse_event("error", {"code": "stream_crash", "message": str(exc)})
        finally:
            active_turns.pop(turn.turn_id, None)
            pending_approvals.pop(turn.turn_id, None)
            trace_turn_outcome(turn.status, turn.error)
            await flush_now()
            clear_trace()
            if final_answer:
                await append_message(
                    conversation_id=conv_id,
                    role="assistant",
                    content=final_answer,
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
