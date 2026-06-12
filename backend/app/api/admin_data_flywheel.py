"""Admin 数据飞轮 API。"""

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_current_user, get_db, require_admin
from app.core.database import SessionLocal
from app.models.farm import Farm
from app.models.user import User
from app.services.data_flywheel_service import (
    SAMPLE_TYPE_SESSION_TURN,
    add_sample_label,
    build_case_draft,
    delete_sample_label,
    export_sample_jsonl,
    get_session_annotation_detail,
    get_sample_detail,
    list_samples,
    resolve_sample_label,
)
from app.services.data_flywheel_session_review_service import get_session_review
from app.services.data_flywheel_session_sync_service import sync_session_events

router = APIRouter(
    prefix="/admin/data-flywheel",
    tags=["admin-data-flywheel"],
    dependencies=[Depends(require_admin)],
)

AGENT_EVENT_BASE_DIR = Path("data/agent-events")
_SYNC_JOBS: dict[str, dict[str, Any]] = {}


class LabelRequest(BaseModel):
    label: str
    sample_type: str = SAMPLE_TYPE_SESSION_TURN
    session_id: str | None = None
    turn_id: int | None = None
    request_id: str | None = None
    comment: str | None = None


class BadCaseRequest(BaseModel):
    label: str | None = None
    comment: str | None = None


class ExportJsonlRequest(BaseModel):
    sample_id: str


class CaseDraftRequest(BaseModel):
    target_type: str = "evaluation_replay"


class SyncSessionsRequest(BaseModel):
    session_id: str | None = None
    only_missing: bool = True
    limit: int = 100
    run_inline: bool = False


@router.get("/samples")
def list_admin_data_flywheel_samples(
    sample_type: str = Query(SAMPLE_TYPE_SESSION_TURN),
    label: str | None = Query(None),
    session_id: str | None = Query(None),
    request_id: str | None = Query(None),
    q: str | None = Query(None),
    unannotated_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """列出当前农场的 Agent 数据飞轮样本。"""
    try:
        return list_samples(
            db,
            farm_id=farm.id,
            sample_type=sample_type or SAMPLE_TYPE_SESSION_TURN,
            label=label,
            session_id=session_id,
            request_id=request_id,
            q=q,
            unannotated_only=unannotated_only,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/samples/{sample_id}")
def get_admin_data_flywheel_sample(
    sample_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """获取单个数据飞轮样本详情。"""
    try:
        return get_sample_detail(db, farm_id=farm.id, sample_id=sample_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/sessions/{session_id}/review")
def get_admin_data_flywheel_session_review(
    session_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """获取单个会话的完整 turn 审阅时间线。"""
    return get_session_review(db, farm_id=farm.id, session_id=session_id)


@router.get("/sessions/{session_id}/annotations")
def get_admin_data_flywheel_session_annotations(
    session_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """获取单个会话的会话级标注。"""
    try:
        return get_session_annotation_detail(db, farm_id=farm.id, session_id=session_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/sync-sessions")
def sync_admin_data_flywheel_sessions(
    background_tasks: BackgroundTasks,
    body: SyncSessionsRequest | None = None,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """将数据库已有会话补齐同步到 Agent JSONL 事件日志。"""
    payload = body or SyncSessionsRequest()
    if payload.run_inline:
        return {
            "mode": "inline",
            **sync_session_events(
                db,
                farm_id=farm.id,
                session_id=payload.session_id,
                only_missing=payload.only_missing,
                event_base_dir=AGENT_EVENT_BASE_DIR,
                limit=payload.limit,
            ),
        }

    job_id = f"session-sync-{uuid.uuid4().hex[:12]}"
    _SYNC_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "mode": "background",
        "farm_id": farm.id,
        "session_id": payload.session_id,
        "result": None,
        "error": None,
    }
    background_tasks.add_task(
        run_session_events_sync_job,
        job_id=job_id,
        farm_id=farm.id,
        session_id=payload.session_id,
        only_missing=payload.only_missing,
        event_base_dir=AGENT_EVENT_BASE_DIR,
        limit=payload.limit,
    )
    return _SYNC_JOBS[job_id]


@router.get("/sync-sessions/{job_id}")
def get_admin_data_flywheel_sync_job(job_id: str) -> dict[str, Any]:
    """查询会话事件补齐同步任务状态。"""
    job = _SYNC_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail={"code": "SYNC_JOB_NOT_FOUND"})
    return job


def run_session_events_sync_job(
    *,
    job_id: str,
    farm_id: int,
    session_id: str | None,
    only_missing: bool,
    event_base_dir: str | Path,
    limit: int,
) -> None:
    """后台执行会话事件补齐任务。"""
    job = _SYNC_JOBS.get(job_id)
    if job is not None:
        job["status"] = "running"
    db = SessionLocal()
    try:
        result = sync_session_events(
            db,
            farm_id=farm_id,
            session_id=session_id,
            only_missing=only_missing,
            event_base_dir=event_base_dir,
            limit=limit,
        )
    except Exception as exc:
        if job is not None:
            job["status"] = "failed"
            job["error"] = str(exc)
        raise
    finally:
        db.close()
    if job is not None:
        job["status"] = "completed"
        job["result"] = result


@router.post("/samples/{sample_id}/labels")
def add_admin_data_flywheel_label(
    sample_id: str,
    body: LabelRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """新增或更新样本质量标注。"""
    try:
        return add_sample_label(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            label=body.label,
            sample_type=body.sample_type or SAMPLE_TYPE_SESSION_TURN,
            session_id=body.session_id,
            turn_id=body.turn_id,
            request_id=body.request_id,
            comment=body.comment,
            annotator_id=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.delete("/samples/{sample_id}/labels/{label_id}")
def delete_admin_data_flywheel_label(
    sample_id: str,
    label_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, int | bool]:
    """删除当前农场样本的一条人工标注。"""
    try:
        return delete_sample_label(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            label_id=label_id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/samples/{sample_id}/labels/{label_id}/resolve")
def resolve_admin_data_flywheel_label(
    sample_id: str,
    label_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """将当前农场样本的一条人工标注标记为已解决。"""
    try:
        return resolve_sample_label(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            label_id=label_id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/samples/{sample_id}/bad-case")
def mark_admin_data_flywheel_bad_case(
    sample_id: str,
    body: BadCaseRequest | None = None,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """将样本快速标记为 bad case。"""
    label = (body.label if body else None) or "bad_reply"
    if label.strip() == "" or label == "good_reply":
        label = "bad_reply"
    try:
        return add_sample_label(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            label=label,
            sample_type=SAMPLE_TYPE_SESSION_TURN,
            comment=body.comment if body else None,
            annotator_id=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/export-jsonl")
def export_admin_data_flywheel_jsonl(
    body: ExportJsonlRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, str]:
    """导出单条样本 JSONL 内容。"""
    try:
        return export_sample_jsonl(db, farm_id=farm.id, sample_id=body.sample_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/samples/{sample_id}/case-draft")
def build_admin_data_flywheel_case_draft(
    sample_id: str,
    body: CaseDraftRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """从样本生成评测用例草稿。"""
    try:
        return build_case_draft(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            target_type=body.target_type,
            created_by=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


def _http_error(exc: ValueError) -> HTTPException:
    code = str(exc)
    status_code = 404 if code in {"SAMPLE_NOT_FOUND", "LABEL_NOT_FOUND"} else 400
    return HTTPException(status_code=status_code, detail={"code": code})


__all__ = ["router"]
