"""会话端点：GET /api/agri_backend_v2/conversations + GET /api/agri_backend_v2/conversations/{id}。"""

from __future__ import annotations

import logging

from fastapi import Header, HTTPException, Query

from agent.api import api_router
from agent.auth import parse_identity
from agent.platforms.persistence.mongo.chat_store import get_conversation, list_conversations

logger = logging.getLogger(__name__)


@api_router.get("/conversations")
async def conversations_list(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """List conversations with pagination."""
    try:
        identity = parse_identity(authorization)
        return await list_conversations(
            limit=limit,
            cursor=cursor,
            user_id=identity["user_id"],
            farm_id=identity["farm_id"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("conversations list failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/conversations/{conversation_id}")
async def conversation_detail(
    conversation_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    before: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """Get conversation messages."""
    try:
        identity = parse_identity(authorization)
        result = await get_conversation(
            conversation_id,
            limit=limit,
            before=before,
            user_id=identity["user_id"],
            farm_id=identity["farm_id"],
        )
        if not result.get("items"):
            raise HTTPException(
                404, {"detail": "conversation not found", "code": "not_found"}
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("conversation detail failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})
