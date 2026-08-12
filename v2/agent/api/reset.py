"""POST /api/v2/reset — 清空会话记忆。"""

from __future__ import annotations

from pydantic import BaseModel

from agent.api import api_router
from agent.core import memory
from agent.auth import parse_identity
from fastapi import Header
from agent.infra.coordination import scope_hash


class ResetRequest(BaseModel):
    conversation_id: str = "default"


@api_router.post("/reset")
def reset(req: ResetRequest, authorization: str | None = Header(default=None)) -> dict:
    identity = parse_identity(authorization)
    memory.reset_conversation(
        scope_hash(identity["user_id"], identity["farm_id"], req.conversation_id)
    )
    return {"ok": True, "conversation_id": req.conversation_id}
