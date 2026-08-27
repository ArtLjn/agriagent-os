"""POST /api/v2/reset — 清空会话记忆。"""

from __future__ import annotations

from pydantic import BaseModel

from agent.api import api_router
from agent.domains.harness.memory import service as memory
from agent.auth import parse_identity, require_identity_permission
from fastapi import Header
from shared.roles import Permission


class ResetRequest(BaseModel):
    conversation_id: str = "default"


@api_router.post("/reset")
async def reset(
    req: ResetRequest,
    authorization: str | None = Header(default=None),
) -> dict:
    identity = require_identity_permission(
        parse_identity(authorization), Permission.CONVERSATION_WRITE
    )
    result = await memory.reset_session(
        req.conversation_id,
        user_id=identity["user_id"],
        farm_id=identity["farm_id"],
    )
    return {
        **result,
        "conversation_id": req.conversation_id,
        "reset_generation": result.get("reset_generation", 1),
        "source_status": result.get("source_status", result.get("status", "empty")),
    }
