"""Trace 端点：GET /api/agri_backend_v2/traces 系列。"""

from __future__ import annotations

import logging

from fastapi import Header, HTTPException, Query

from agent.api import api_router
from agent.auth import parse_identity
from agent.infra.trace.store import (
    get_trace_events,
    get_trace_nodes,
    get_trace_summary,
    get_trace_timeline,
    list_traces,
)

logger = logging.getLogger(__name__)


@api_router.get("/traces")
async def traces_list(
    conversation_id: str | None = Query(default=None),
    turn_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """List trace request summaries."""
    try:
        identity = parse_identity(authorization)
        return await list_traces(
            conversation_id=conversation_id,
            turn_id=turn_id,
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


@api_router.get("/traces/{trace_id}/nodes")
async def trace_nodes_formal(
    trace_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    include_payload: bool = Query(default=False),
    include_resource_spans: bool = Query(default=False),
    span_kind: str | None = Query(default=None),
    node_type: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """使用正式 trace_id 查询内部执行节点。"""
    try:
        identity = parse_identity(authorization)
        return await get_trace_nodes(
            trace_id,
            limit=limit,
            include_payload=include_payload,
            include_resource_spans=include_resource_spans,
            span_kind=span_kind,
            node_type=node_type,
            user_id=identity["user_id"],
            farm_uid=identity["farm_uid"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("trace nodes query failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/traces/{trace_id}/events")
async def trace_events(
    trace_id: str,
    after_seq: int | None = Query(default=None, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    include_payload: bool = Query(default=False),
    authorization: str | None = Header(default=None),
) -> dict:
    """查询持久化 SSE 事件账本；traceEvents 不可用时返回证据状态。"""
    try:
        identity = parse_identity(authorization)
        return await get_trace_events(
            trace_id,
            after_seq=after_seq,
            limit=limit,
            include_payload=include_payload,
            user_id=identity["user_id"],
            farm_uid=identity["farm_uid"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("trace events query failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/traces/{trace_id}/timeline")
async def trace_timeline(
    trace_id: str,
    limit: int = Query(default=400, ge=1, le=2000),
    include_payload: bool = Query(default=False),
    include_resource_spans: bool = Query(default=False),
    authorization: str | None = Header(default=None),
) -> dict:
    """查询按时间合并的 Trace 节点和 SSE 事件。"""
    try:
        identity = parse_identity(authorization)
        return await get_trace_timeline(
            trace_id,
            limit=limit,
            include_payload=include_payload,
            include_resource_spans=include_resource_spans,
            user_id=identity["user_id"],
            farm_uid=identity["farm_uid"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("trace timeline query failed: %s", exc)
        raise HTTPException(500, {"detail": str(exc), "code": "internal"})


@api_router.get("/traces/{request_id}")
async def trace_nodes(
    request_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    include_payload: bool = Query(default=False),
    include_resource_spans: bool = Query(default=False),
    span_kind: str | None = Query(default=None),
    node_type: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> dict:
    """Get all trace nodes for a request."""
    try:
        identity = parse_identity(authorization)
        result = await get_trace_nodes(
            request_id,
            limit=limit,
            include_payload=include_payload,
            include_resource_spans=include_resource_spans,
            span_kind=span_kind,
            node_type=node_type,
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
