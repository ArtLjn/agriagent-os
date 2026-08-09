"""POST /api/v2/reset — 清空会话记忆。"""

from __future__ import annotations

from pydantic import BaseModel

from agent.api import api_router
from agent.core import memory


class ResetRequest(BaseModel):
    conversation_id: str = "default"


@api_router.post("/reset")
def reset(req: ResetRequest) -> dict:
    memory.reset_conversation(req.conversation_id)
    return {"ok": True, "conversation_id": req.conversation_id}
