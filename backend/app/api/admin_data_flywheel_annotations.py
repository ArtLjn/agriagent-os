"""Admin 数据飞轮标注 API。"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_current_user, get_db, require_admin
from app.models.farm import Farm
from app.models.user import User
from app.modules.data_flywheel.service import (
    SAMPLE_TYPE_SESSION_TURN,
    accept_sample_prelabel,
    add_sample_label,
    delete_sample_label,
    export_sample_jsonl,
    reject_sample_prelabel,
    resolve_sample_label,
)

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


class AcceptPrelabelRequest(BaseModel):
    labels: list[str] | None = None
    comment: str | None = None


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


@router.post("/samples/{sample_id}/prelabels/{prelabel_id}/accept")
def accept_admin_data_flywheel_prelabel(
    sample_id: str,
    prelabel_id: int,
    body: AcceptPrelabelRequest | None = None,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """采纳 LLM 预标注，可由管理员修改标签和备注。"""
    payload = body or AcceptPrelabelRequest()
    try:
        return accept_sample_prelabel(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            prelabel_id=prelabel_id,
            labels=payload.labels,
            comment=payload.comment,
            annotator_id=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/samples/{sample_id}/prelabels/{prelabel_id}/reject")
def reject_admin_data_flywheel_prelabel(
    sample_id: str,
    prelabel_id: int,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """拒绝 LLM 预标注，不写入人工质量标签。"""
    try:
        return reject_sample_prelabel(
            db,
            farm_id=farm.id,
            sample_id=sample_id,
            prelabel_id=prelabel_id,
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


def _http_error(exc: ValueError) -> HTTPException:
    if exc.args and isinstance(exc.args[0], dict):
        return HTTPException(status_code=400, detail=exc.args[0])
    code = str(exc)
    status_code = (
        404 if code in {"SAMPLE_NOT_FOUND", "LABEL_NOT_FOUND", "PRELABEL_NOT_FOUND"} else 400
    )
    return HTTPException(status_code=status_code, detail={"code": code})
