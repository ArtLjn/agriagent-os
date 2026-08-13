"""Trace 端点：GET /api/v2/traces 系列。"""

from __future__ import annotations

import logging

from fastapi import Header, HTTPException, Query

from agent.api import api_router
from agent.auth import parse_identity
from agent.infra.trace.store import get_trace_nodes, get_trace_summary, list_traces

logger = logging.getLogger(__name__)


@api_router.get("/traces")
async def traces_list(
    conversation_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """List trace request summaries."""
    try:
        identity = parse_identity(authorization)
        return await list_traces(
            conversation_id=conversation_id,
            limit=limit,
            cursor=cursor,
            user_id=identity["user_id"],
            farm_uid=identity["farm_uid"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("traces list failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/traces/{request_id}")
async def trace_nodes(
    request_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    authorization: str | None = Header(default=None),
) -> dict:
    """Get all trace nodes for a request."""
    try:
        identity = parse_identity(authorization)
        result = await get_trace_nodes(
            request_id,
            limit=limit,
            user_id=identity["user_id"],
            farm_uid=identity["farm_uid"],
        )
        if not result.get("nodes"):
            raise HTTPException(404, {"detail": "trace not found", "code": "not_found"})
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("trace nodes failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/traces/{request_id}/summary")
async def trace_summary(
    request_id: str, authorization: str | None = Header(default=None)
) -> dict:
    """Get aggregated trace summary for a request."""
    try:
        identity = parse_identity(authorization)
        result = await get_trace_summary(
            request_id,
            user_id=identity["user_id"],
            farm_uid=identity["farm_uid"],
        )
        if result is None:
            raise HTTPException(404, {"detail": "trace not found", "code": "not_found"})
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("trace summary failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})
