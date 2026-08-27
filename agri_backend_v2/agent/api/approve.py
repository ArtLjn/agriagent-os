"""POST /api/v2/approve — 决议 HITL gate。"""

from __future__ import annotations

from fastapi import Header, HTTPException
from pydantic import BaseModel

from agent.api import api_router
from agent.auth import parse_identity, require_identity_permission
from agent.platforms.persistence.redis.turn_store import get_turn, resolve_approval
from shared.roles import Permission


class ApproveRequest(BaseModel):
    turn_id: str
    decision: bool
    reason: str = ""


@api_router.post("/approve")
async def approve(
    req: ApproveRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    """Resolve HITL gate for a pending turn."""
    turn = await get_turn(req.turn_id)
    if turn is None:
        raise HTTPException(404, {"code": "turn_not_found", "message": "turn 不存在"})
    identity = require_identity_permission(
        parse_identity(authorization), Permission.TURN_APPROVE
    )
    if not _same_identity(turn, identity):
        raise HTTPException(
            403, {"code": "turn_forbidden", "message": "无权操作该 turn"}
        )
    resolved = await resolve_approval(req.turn_id, req.decision, req.reason)
    if not resolved:
        raise HTTPException(
            409,
            {"code": "approval_already_resolved", "message": "审批已经完成或已过期"},
        )
    return {"ok": True, "turn_id": req.turn_id, "decision": req.decision}


def _same_identity(turn: dict[str, str], identity: dict) -> bool:
    """优先用 farm_uid 校验，兼容旧 Redis turn 的 farm_id。"""
    if str(turn.get("user_id", "")) != str(identity["user_id"]):
        return False
    if turn.get("farm_uid"):
        return str(turn["farm_uid"]) == str(identity["farm_uid"])
    return int(turn.get("farm_id", 1)) == int(identity["farm_id"])
