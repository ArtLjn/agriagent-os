"""Admin 数据飞轮 API。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_current_user, get_db, require_admin
from app.models.farm import Farm
from app.models.user import User
from app.services.data_flywheel_service import (
    SAMPLE_TYPE_SESSION_TURN,
    add_sample_label,
    build_case_draft,
    export_sample_jsonl,
    get_sample_detail,
    list_samples,
)
from app.services.data_flywheel_session_review_service import get_session_review

router = APIRouter(
    prefix="/admin/data-flywheel",
    tags=["admin-data-flywheel"],
    dependencies=[Depends(require_admin)],
)


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
    status_code = 404 if code == "SAMPLE_NOT_FOUND" else 400
    return HTTPException(status_code=status_code, detail={"code": code})


__all__ = ["router"]
