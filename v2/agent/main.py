"""FastAPI entry point.

Endpoints:
  GET  /                → Web UI (static/index.html)
  POST /chat            → SSE stream of ReAct events
  POST /approve         → Resolve HITL gate (decision: bool, reason: str)
  POST /reset           → Wipe conversation memory
  GET  /health          → Liveness check
  GET  /turns/{turn_id} → Turn status (polling fallback)
  GET  /conversations   → Conversation list
  GET  /conversations/{id} → Conversation detail
  GET  /traces          → Trace request list
  GET  /traces/{request_id} → Trace node detail
  GET  /traces/{request_id}/summary → Trace aggregated summary

Approval flow:
  1. /chat starts run_turn, which yields approval_required event with turn_id.
  2. UI shows approve/reject buttons, POSTs to /approve with turn_id + decision.
  3. main.py resolves the future for that turn_id; run_turn unblocks.

Run: cd v2/agent && python main.py
"""
from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

# 允许从 v2/agent/ 直接 `python main.py`：把 v2/ 父目录加入 sys.path
_PARENT = str(Path(__file__).resolve().parent.parent)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.core import memory
from agent.core.react import run_turn
from agent.core.turn import Turn
from agent.infra.chat_store import (
    append_message,
    check_connection,
    close,
    list_conversations,
    get_conversation,
)
from agent.infra.logging import get_logger, setup_logging
from agent.infra.sse import sse_event
from agent.infra.trace import init_trace, clear_trace, start_trace_system, stop_trace_system
from agent.infra.trace.store import list_traces, get_trace_nodes, get_trace_summary

setup_logging(app_name="agent")
logger = get_logger(__name__)

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: check MongoDB, start trace system. Shutdown: flush trace, close client."""
    await check_connection()
    await start_trace_system()
    yield
    await stop_trace_system()
    await close()


app = FastAPI(title="farm-manager agent", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Pending HITL approvals keyed by turn_id. Each value is a Future that
# /approve resolves with (decision: bool, reason: str).
_pending_approvals: dict[str, asyncio.Future[tuple[bool, str]]] = {}
# Live turn snapshots for /turns/{turn_id} status polling.
_active_turns: dict[str, Turn] = {}


# ─── Pydantic request models ─────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


class ApproveRequest(BaseModel):
    turn_id: str
    decision: bool
    reason: str = ""


class ResetRequest(BaseModel):
    conversation_id: str = "default"


# ─── Approval waiter ────────────────────────────────────────────────


async def _approval_waiter(turn_id: str) -> tuple[bool, str]:
    """Block until /approve resolves the future for this turn_id."""
    loop = asyncio.get_running_loop()
    if turn_id not in _pending_approvals:
        _pending_approvals[turn_id] = loop.create_future()
    return await _pending_approvals[turn_id]


# ─── Endpoints ───────────────────────────────────────────────────────


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "pending_approvals": len(_pending_approvals)}


@app.post("/chat")
async def chat(req: ChatRequest) -> StreamingResponse:
    """Start a ReAct turn and stream events back as SSE."""
    # Auto-generate conversation_id if user sent "default" and wants fresh.
    conv_id = req.conversation_id or "default"
    turn = Turn(conversation_id=conv_id, user_input=req.message)
    _active_turns[turn.turn_id] = turn

    # 落库 user message（不阻塞 stream；失败 infra 内部已降级 warning）
    await append_message(
        conversation_id=conv_id,
        role="user",
        content=req.message,
    )

    async def event_stream() -> AsyncGenerator[str, None]:
        final_answer = ""
        init_trace(conversation_id=conv_id, turn_id=turn.turn_id)
        try:
            async for event in run_turn(turn, _approval_waiter):
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
            _active_turns.pop(turn.turn_id, None)
            _pending_approvals.pop(turn.turn_id, None)
            clear_trace()
            # 落库 assistant message（如果有最终答案）
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
            "X-Accel-Buffering": "no",  # disable proxy buffering
        },
    )


@app.post("/approve")
async def approve(req: ApproveRequest) -> dict:
    """Resolve HITL gate for a pending turn."""
    future = _pending_approvals.get(req.turn_id)
    if future is None:
        raise HTTPException(404, f"no pending approval for turn_id={req.turn_id}")
    if future.done():
        raise HTTPException(409, f"approval already resolved for turn_id={req.turn_id}")
    future.set_result((req.decision, req.reason))
    return {"ok": True, "turn_id": req.turn_id, "decision": req.decision}


@app.post("/reset")
def reset(req: ResetRequest) -> dict:
    memory.reset_conversation(req.conversation_id)
    return {"ok": True, "conversation_id": req.conversation_id}


@app.get("/turns/{turn_id}")
def turn_status(turn_id: str) -> dict:
    turn = _active_turns.get(turn_id)
    if turn is None:
        raise HTTPException(404, f"turn not found: {turn_id}")
    return turn.snapshot()


# ─── Conversation endpoints ─────────────────────────────────────────


@app.get("/conversations")
async def conversations_list(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> dict:
    """List conversations with pagination."""
    try:
        return await list_conversations(limit=limit, cursor=cursor)
    except Exception as exc:
        logger.warning("conversations list failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@app.get("/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    before: str | None = Query(default=None),
) -> dict:
    """Get conversation messages."""
    try:
        result = await get_conversation(
            conversation_id, limit=limit, before=before
        )
        if not result.get("items"):
            raise HTTPException(404, {"detail": "conversation not found", "code": "not_found"})
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("conversation detail failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


# ─── Trace endpoints ────────────────────────────────────────────────


@app.get("/traces")
async def traces_list(
    conversation_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> dict:
    """List trace request summaries."""
    try:
        return await list_traces(
            conversation_id=conversation_id, limit=limit, cursor=cursor
        )
    except Exception as exc:
        logger.warning("traces list failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@app.get("/traces/{request_id}")
async def trace_nodes(
    request_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    """Get all trace nodes for a request."""
    try:
        result = await get_trace_nodes(request_id, limit=limit)
        if not result.get("nodes"):
            raise HTTPException(404, {"detail": "trace not found", "code": "not_found"})
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("trace nodes failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@app.get("/traces/{request_id}/summary")
async def trace_summary(request_id: str) -> dict:
    """Get aggregated trace summary for a request."""
    try:
        result = await get_trace_summary(request_id)
        if result is None:
            raise HTTPException(404, {"detail": "trace not found", "code": "not_found"})
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("trace summary failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


# ─── Main ────────────────────────────────────────────────────────────


def main() -> None:
    import uvicorn

    logger.info("starting agent on http://127.0.0.1:8000")
    uvicorn.run(
        "agent.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
