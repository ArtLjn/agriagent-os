"""Admin Trace 查询 API — 链路查询、Gantt 时间线、清理。"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.evaluation.diagnostics import SkillDiagnosticService
from app.models.trace import TraceRecord

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/admin",
    tags=["admin-trace"],
    dependencies=[Depends(require_admin)],
)


class TimelineNode(BaseModel):
    node_type: str
    node_name: str
    duration_ms: int | None
    status: str
    token_usage: dict | None = None
    start_time: str | None = None
    error_message: str | None = None
    input_data: Any = None
    output_data: Any = None


class TimelineRound(BaseModel):
    round_index: int
    nodes: list[TimelineNode]


class TimelineResponse(BaseModel):
    request_id: str
    rounds: list[TimelineRound]


@router.get("/traces")
def list_traces(
    request_id: str | None = Query(None),
    session_id: str | None = Query(None),
    farm_id: int | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """查询 trace 记录列表。"""
    query = db.query(TraceRecord)
    if request_id:
        query = query.filter(TraceRecord.request_id == request_id)
    if session_id:
        query = query.filter(TraceRecord.session_id == session_id)
    if farm_id:
        query = query.filter(TraceRecord.farm_id == farm_id)

    total = query.count()
    items = (
        query.order_by(TraceRecord.created_at.desc()).offset(offset).limit(limit).all()
    )

    return {
        "items": [
            {
                "id": r.id,
                "request_id": r.request_id,
                "session_id": r.session_id,
                "farm_id": r.farm_id,
                "round_index": r.round_index,
                "node_type": r.node_type,
                "node_name": r.node_name,
                "duration_ms": r.duration_ms,
                "status": r.status,
                "token_usage": r.token_usage,
                "error_message": r.error_message,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in items
        ],
        "total": total,
    }


@router.get("/traces/{request_id}/timeline", response_model=TimelineResponse)
def get_timeline(request_id: str, db: Session = Depends(get_db)) -> TimelineResponse:
    """获取某次请求的 Gantt 时间线数据。"""
    records = (
        db.query(TraceRecord)
        .filter(TraceRecord.request_id == request_id)
        .order_by(TraceRecord.round_index, TraceRecord.id)
        .all()
    )
    if not records:
        return TimelineResponse(request_id=request_id, rounds=[])

    rounds_map: dict[int, list[TimelineNode]] = defaultdict(list)
    for r in records:
        rounds_map[r.round_index].append(
            TimelineNode(
                node_type=r.node_type,
                node_name=r.node_name,
                duration_ms=r.duration_ms,
                status=r.status,
                token_usage=_coerce_token_usage(r.token_usage),
                start_time=_format_datetime(r.start_time),
                error_message=r.error_message,
                input_data=r.input_data,
                output_data=r.output_data,
            )
        )

    rounds = [
        TimelineRound(round_index=idx, nodes=nodes)
        for idx, nodes in sorted(rounds_map.items())
    ]
    return TimelineResponse(request_id=request_id, rounds=rounds)


@router.get("/traces/{request_id}/diagnostics")
def get_trace_diagnostics(request_id: str, db: Session = Depends(get_db)) -> dict:
    """获取 Skill 诊断汇总。"""
    records = (
        db.query(TraceRecord)
        .filter(TraceRecord.request_id == request_id)
        .order_by(TraceRecord.round_index, TraceRecord.id)
        .all()
    )
    report = SkillDiagnosticService().build_report(request_id, records)
    return {
        "request_id": report.request_id,
        "tool_selection": report.tool_selection,
        "context_injection": report.context_injection,
        "tool_calls": report.tool_calls,
        "pending_actions": report.pending_actions,
        "pending_lifecycle": report.pending_lifecycle,
        "context_dependencies": report.context_dependencies,
        "context_dependency_diagnostic": report.context_dependency_diagnostic,
        "tool_not_called_reason": report.tool_not_called_reason,
        "pending_action_diagnostic": report.pending_action_diagnostic,
        "reflection_checks": report.reflection_checks,
        "reflection_diagnostic": report.reflection_diagnostic,
        "errors": report.errors,
        "final_response": report.final_response,
        "drilldown_links": report.drilldown_links,
    }


def _format_datetime(value: Any) -> str | None:
    """将数据库时间值统一转为 API 响应字符串。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _coerce_token_usage(value: Any) -> dict | None:
    """兼容旧数据或测试中保存为 JSON 字符串的 token_usage。"""
    if value is None or isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


@router.get("/traces/{request_id}/nodes/{node_id}")
def get_node_detail(
    request_id: str, node_id: int, db: Session = Depends(get_db)
) -> dict:
    """获取节点详情（完整 input/output）。"""
    record = (
        db.query(TraceRecord)
        .filter(TraceRecord.request_id == request_id, TraceRecord.id == node_id)
        .first()
    )
    if not record:
        return {"error": "节点不存在"}
    return {
        "id": record.id,
        "request_id": record.request_id,
        "round_index": record.round_index,
        "node_type": record.node_type,
        "node_name": record.node_name,
        "input_data": record.input_data,
        "output_data": record.output_data,
        "duration_ms": record.duration_ms,
        "token_usage": record.token_usage,
        "status": record.status,
        "error_message": record.error_message,
        "start_time": record.start_time,
        "end_time": record.end_time,
    }


@router.delete("/traces")
def delete_traces(
    before: str = Query(..., description="删除此日期之前的 trace (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> dict:
    """按日期清理历史 trace。"""
    cutoff = datetime.fromisoformat(before)
    deleted = (
        db.query(TraceRecord)
        .filter(TraceRecord.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    logger.info("Admin 删除 trace | before=%s deleted=%d", before, deleted)
    return {"deleted": deleted}


__all__ = ["router"]
