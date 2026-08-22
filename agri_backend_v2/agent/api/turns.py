"""GET /api/v2/turns/{turn_id} — Turn 状态轮询。"""

from __future__ import annotations

from fastapi import Header, HTTPException, Query
from fastapi.responses import StreamingResponse

from agent.api import api_router
from agent.auth import parse_identity
from agent.domains.harness.runtime.turn import StopReason
from agent.domains.harness.runtime.projection import (
    ProjectionPermissionError,
    project_event,
    resolve_presentation_profile,
)
from agent.platforms.persistence.redis import sse
from agent.platforms.persistence.redis.sse import sse_event
from agent.platforms.persistence.redis.turn_store import (
    get_turn,
    legacy_status_fields,
    publish_event,
    resolve_event_seq,
    stream_events,
)
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
    legacy_status_fields(turn)
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
    after_seq: int | None = Query(default=None, ge=0),
    authorization: str | None = Header(default=None),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    viewer_authorization: str | None = Header(default=None, alias="X-Viewer-Authorization"),
    presentation_profile: str | None = Header(default=None, alias="X-SSE-Presentation-Profile"),
) -> StreamingResponse:
    turn = await get_turn(turn_id)
    if turn is None:
        raise HTTPException(404, {"code": "turn_not_found", "message": "turn 不存在"})
    checked_identity = _check_access(turn, authorization)
    execution_identity = checked_identity or {
        "user_id": turn.get("user_id", ""),
        "farm_uid": turn.get("farm_uid", ""),
        "role": "user",
    }
    viewer_identity = execution_identity
    viewer_token = viewer_authorization if isinstance(viewer_authorization, str) else None
    requested_profile = presentation_profile if isinstance(presentation_profile, str) else None
    if viewer_token:
        viewer_identity = parse_identity(viewer_token)
        if viewer_identity.get("role") != "admin":
            raise HTTPException(403, {"code": "viewer_forbidden", "message": "viewer 无权查看 Agent 调试流"})
    try:
        resolved_profile = resolve_presentation_profile(
            execution_identity=execution_identity,
            viewer_identity=viewer_identity,
            requested=requested_profile,
        )
    except ProjectionPermissionError as exc:
        raise HTTPException(403, {"code": "projection_forbidden", "message": str(exc)}) from exc
    replay_after_seq = after_seq
    if replay_after_seq is None and last_event_id:
        replay_after_seq = await resolve_event_seq(turn_id, last_event_id)
    if replay_after_seq is None:
        replay_after_seq = 0

    async def event_stream():
        async for event in stream_events(turn_id, after_seq=replay_after_seq):
            projected = project_event(
                event,
                profile=resolved_profile,
                execution_identity=execution_identity,
                viewer_identity=viewer_identity,
            )
            if projected is None:
                continue
            payload = {**projected["data"], "seq": event["seq"]}
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
                "presentation_profile",
                "viewer_user_id",
                "execution_user_id",
                "impersonation",
            ):
                if field in projected:
                    payload[field] = projected[field]
            yield sse_event(
                projected["type"],
                payload,
                event_id=projected.get("event_id", ""),
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
        "terminated",
        "failed",
        "rejected",
        "cancelled",
        "timeout",
    }:
        raise HTTPException(
            409, {"code": "turn_already_terminal", "message": "turn 已结束"}
        )
    await update_turn(
        turn_id,
        status="cancelled",
        phase="terminal",
        stop_reason=StopReason.USER_CANCELLED.value,
        error_code="turn_cancelled",
        error_message="本轮任务已取消",
        finalization_pending=turn.get("status") not in {"accepted", "queued"},
    )
    await publish_event(
        turn_id,
        {
            "type": "cancelled",
            "data": {"code": "turn_cancelled", "turn_id": turn_id},
        },
    )
    if turn.get("status") in {"accepted", "queued"}:
        await publish_event(
            turn_id,
            {"type": "final_answer", "data": {"text": "本轮任务已取消。"}},
        )
        await publish_event(
            turn_id,
            sse.turn_terminated(
                turn_id,
                reason="user_cancelled",
                message="本轮任务已取消",
                step_count=int(turn.get("step_count", 0) or 0),
                status="cancelled",
            ),
        )
        await publish_event(
            turn_id,
            {"type": "done", "data": {"status": "cancelled", "turn_id": turn_id, "stop_reason": "user_cancelled"}},
        )
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
        await update_turn(turn_id, finalization_pending=False)
    return {"ok": True, "turn_id": turn_id, "status": "cancelled"}


def _check_access(turn: dict[str, str], authorization: str | None) -> dict:
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
    return identity
