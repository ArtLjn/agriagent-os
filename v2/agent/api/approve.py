"""POST /api/v2/approve — 决议 HITL gate。"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

from agent.api import api_router
from agent.deps import pending_approvals


class ApproveRequest(BaseModel):
    turn_id: str
    decision: bool
    reason: str = ""


@api_router.post("/approve")
async def approve(req: ApproveRequest) -> dict:
    """Resolve HITL gate for a pending turn."""
    future = pending_approvals.get(req.turn_id)
    if future is None:
        raise HTTPException(404, f"no pending approval for turn_id={req.turn_id}")
    if future.done():
        raise HTTPException(409, f"approval already resolved for turn_id={req.turn_id}")
    future.set_result((req.decision, req.reason))
    return {"ok": True, "turn_id": req.turn_id, "decision": req.decision}
