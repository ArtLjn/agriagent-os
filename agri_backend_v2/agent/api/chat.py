"""POST /api/agri_backend_v2/chat — SSE ReAct 事件流。"""

from __future__ import annotations

import hashlib
import uuid
import logging

from fastapi import Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.api import api_router
from agent.auth import ensure_mcp_credentials, parse_identity
from agent.domains.harness.runtime.turn import Turn
from agent.platforms.persistence.mongo.chat_store import append_message
from agent.platforms.persistence.redis.coordination import (
    CoordinationError,
    TurnAdmissionError,
    admit_turn,
    release_turn,
    scope_hash,
)
from agent.platforms.persistence.redis.sse import sse_event
from agent.domains.harness.observability.trace.context import trace_id_for_turn
from agent.platforms.persistence.redis.turn_store import (
    claim_idempotency,
    dispatch_turn,
    get_turn,
    publish_event,
    save_turn,
    stream_events,
    update_turn,
)

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"
    client_request_id: str | None = None


@api_router.post("/chat")
async def chat(
    req: ChatRequest,
    authorization: str | None = Header(default=None),
    after_seq: int = Query(default=0, ge=0),
) -> StreamingResponse:
    """Create a durable turn and stream replayable Redis events."""
    conv_id = req.conversation_id or "default"
    identity = parse_identity(authorization)
    ensure_mcp_credentials()
    scope = scope_hash(identity["user_id"], identity["farm_id"], conv_id)
    request_id = req.client_request_id or uuid.uuid4().hex
    request_fingerprint = hashlib.sha256(
        f"{conv_id}|{req.message}".encode("utf-8")
    ).hexdigest()
    turn = Turn(
        conversation_id=conv_id,
        user_input=req.message,
        user_id=identity["user_id"],
        farm_uid=identity["farm_uid"],
        farm_id=identity["farm_id"],
        role=identity["role"],
        token_id=identity["token_id"],
        scope=identity["scope"],
        agent_token=identity["agent_token"],
        memory_key=scope_hash(identity["user_id"], identity["farm_id"], conv_id),
    )
    trace_id = trace_id_for_turn(turn.turn_id)
    try:
        admission = None
        claimed, existing = await claim_idempotency(
            scope_hash=scope,
            client_request_id=request_id,
            request_fingerprint=request_fingerprint,
            turn_id=turn.turn_id,
        )

        if not claimed:
            if not existing:
                raise HTTPException(409, {"code": "idempotency_state_missing"})
            if existing.get("request_fingerprint") != request_fingerprint:
                raise HTTPException(
                    409,
                    {
                        "code": "idempotency_key_reused",
                        "message": "幂等键已被其他请求使用",
                    },
                )
            existing_turn_id = existing["turn_id"]
            turn_state = await get_turn(existing_turn_id)
            if turn_state is None:
                raise HTTPException(404, {"code": "turn_not_found"})
            turn.turn_id = existing_turn_id
            trace_id = turn_state.get("trace_id") or trace_id_for_turn(existing_turn_id)
            await update_turn(existing_turn_id, reconnect_count=1)
            admission = None
        else:
            admission = await admit_turn(
                turn_id=turn.turn_id,
                user_id=turn.user_id,
                farm_id=turn.farm_id,
                conversation_id=conv_id,
            )
            await save_turn(
                turn,
                scope_hash=scope,
                lease_token=admission.lease.token,
                queued=admission.queued,
                queue_kind=admission.queue_kind,
                trace_id=trace_id,
                client_request_id=request_id,
            )
            prompt_message_id = await append_message(
                conversation_id=conv_id,
                role="user",
                content=req.message,
                turn_id=turn.turn_id,
                trace_id=trace_id,
                message_kind="prompt",
                user_id=identity["user_id"],
                farm_id=identity["farm_id"],
                idempotency_key=f"turn:{turn.turn_id}:user:prompt",
            )
            if not prompt_message_id:
                await update_turn(
                    turn.turn_id,
                    status="failed",
                    error_code="conversation_message_persist_failed",
                )
                if admission.queued:
                    from agent.platforms.persistence.redis.turn_store import remove_from_queues

                    await remove_from_queues(turn.turn_id, scope)
                else:
                    await release_turn(admission.lease)
                from agent.platforms.persistence.redis.turn_store import release_idempotency

                await release_idempotency(scope, request_id)
                raise HTTPException(
                    503,
                    {
                        "code": "conversation_message_persist_failed",
                        "message": "用户消息未能持久化，Turn 未派发",
                    },
                )
            await publish_event(
                turn.turn_id,
                {
                    "type": "queued" if admission.queued else "accepted",
                    "data": {
                        "turn_id": turn.turn_id,
                        "conversation_id": conv_id,
                        "queue": admission.queued,
                    },
                },
            )
            await dispatch_turn(turn.turn_id)
    except TurnAdmissionError as exc:
        from agent.platforms.persistence.redis.turn_store import release_idempotency

        await release_idempotency(scope, request_id)
        status_code = 409 if exc.code.startswith("conversation") else 429
        raise HTTPException(
            status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except CoordinationError as exc:
        from agent.platforms.persistence.redis.turn_store import release_idempotency

        await release_idempotency(scope, request_id)
        raise HTTPException(
            503,
            detail={"code": "coordination_unavailable", "message": str(exc)},
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        if admission is not None:
            if admission.queued:
                from agent.platforms.persistence.redis.turn_store import remove_from_queues

                await remove_from_queues(turn.turn_id, scope)
            else:
                await release_turn(admission.lease)
        from agent.platforms.persistence.redis.turn_store import release_idempotency

        await release_idempotency(scope, request_id)
        raise HTTPException(
            503, {"code": "turn_creation_failed", "message": str(exc)}
        ) from exc

    async def event_stream():
        async for event in stream_events(turn.turn_id, after_seq=after_seq):
            payload = {**event["data"], "seq": event["seq"]}
            for field in (
                "event_id",
                "trace_id",
                "request_id",
                "turn_id",
                "conversation_id",
                "event_type",
                "occurred_at",
                "phase",
                "step",
                "step_index",
                "terminal",
                "status_before",
                "status_after",
            ):
                if field in event:
                    payload[field] = event[field]
            yield sse_event(
                event["type"],
                payload,
                event_id=event.get("event_id", ""),
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
