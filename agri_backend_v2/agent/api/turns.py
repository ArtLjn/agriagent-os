"""GET /api/v2/turns/{turn_id} — Turn 状态轮询。"""

from __future__ import annotations

from fastapi import Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from agent.api import api_router
from agent.auth import parse_identity
from agent.platforms.persistence.redis.sse import sse_event
from agent.platforms.persistence.redis.turn_store import get_turn, publish_event, stream_events
from agent.platforms.persistence.redis.coordination import scope_hash
from agent.platforms.persistence.redis.turn_store import remove_from_queues, update_turn


@api_router.get("/turns/{turn_id}")
async def turn_status(
    turn_id: str,
    authorization: str | None = Header(default=None),
) -> dict:
    turn = await get_turn(turn_id)
    if turn is None:
        raise HTTPException(404, {"code": "turn_not_found", "message": "turn 不存在"})
    _check_access(turn, authorization)
    for name in ("step_count", "last_event_seq"):
        if name in turn:
            try:
                turn[name] = int(turn[name])
            except (TypeError, ValueError):
                pass
    for name in ("conversation_revision", "summary_revision", "reset_generation"):
        try:
            turn[name] = int(turn.get(name, 0) or 0)
        except (TypeError, ValueError):
            turn[name] = 0
    turn["source_status"] = str(
        turn.get("source_status") or turn.get("context_source_status") or "empty"
    )
    turn["context_source_status"] = turn["source_status"]
    if "pending_approval" in turn:
        import json

        try:
            turn["pending_approval"] = json.loads(turn["pending_approval"])
        except (TypeError, json.JSONDecodeError):
            pass
    return turn


@api_router.get("/turns/{turn_id}/events")
async def turn_events(
    turn_id: str,
    after_seq: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
) -> StreamingResponse:
    turn = await get_turn(turn_id)
    if turn is None:
        raise HTTPException(404, {"code": "turn_not_found", "message": "turn 不存在"})
    _check_access(turn, authorization)

    async def event_stream():
        async for event in stream_events(turn_id, after_seq=after_seq):
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
                "conversation_revision",
                "summary_revision",
                "reset_generation",
                "source_status",
                "context_source_status",
            ):
                if field in event:
                    payload[field] = event[field]
            yield sse_event(
                event["type"],
                payload,
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_router.post("/turns/{turn_id}/cancel")
async def cancel_turn(
    turn_id: str,
    authorization: str | None = Header(default=None),
) -> dict:
    turn = await get_turn(turn_id)
    if turn is None:
        raise HTTPException(404, {"code": "turn_not_found", "message": "turn 不存在"})
    _check_access(turn, authorization)
    if turn.get("status") in {
        "completed",
        "failed",
        "rejected",
        "cancelled",
        "timeout",
    }:
        raise HTTPException(
            409, {"code": "turn_already_terminal", "message": "turn 已结束"}
        )
    await update_turn(turn_id, status="cancelled", error_code="turn_cancelled")
    await publish_event(
        turn_id,
        {
            "type": "cancelled",
            "data": {"code": "turn_cancelled", "turn_id": turn_id},
        },
    )
    if turn.get("status") in {"accepted", "queued"}:
        await remove_from_queues(
            turn_id,
            turn.get(
                "scope_hash",
                scope_hash(
                    turn.get("user_id", ""),
                    int(turn.get("farm_id", 1)),
                    turn.get("conversation_id", "default"),
                ),
            ),
        )
    return {"ok": True, "turn_id": turn_id, "status": "cancelled"}


def _check_access(turn: dict[str, str], authorization: str | None) -> None:
    identity = parse_identity(authorization)
    if str(turn.get("user_id", "")) != str(identity["user_id"]):
        raise HTTPException(
            403, {"code": "turn_forbidden", "message": "无权访问该 turn"}
        )
    if turn.get("farm_uid"):
        farm_matches = str(turn["farm_uid"]) == str(identity["farm_uid"])
    else:
        farm_matches = int(turn.get("farm_id", 1)) == int(identity["farm_id"])
    if not farm_matches:
        raise HTTPException(
            403, {"code": "turn_forbidden", "message": "无权访问该 turn"}
        )
