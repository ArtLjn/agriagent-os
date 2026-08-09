"""GET /api/v2/turns/{turn_id} — Turn 状态轮询。"""

from __future__ import annotations

from fastapi import HTTPException

from agent.api import api_router
from agent.deps import active_turns


@api_router.get("/turns/{turn_id}")
def turn_status(turn_id: str) -> dict:
    turn = active_turns.get(turn_id)
    if turn is None:
        raise HTTPException(404, f"turn not found: {turn_id}")
    return turn.snapshot()
