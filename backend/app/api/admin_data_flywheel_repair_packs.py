"""Admin 数据飞轮 repair pack API。"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_farm, get_current_user, get_db, require_admin
from app.models.farm import Farm
from app.models.user import User
from app.services.data_flywheel_service import SAMPLE_TYPE_SESSION_TURN
from app.services.data_flywheel_repair_pack_repository import (
    create_repair_pack,
    get_repair_pack,
    list_repair_candidates,
    mark_repair_pack_resolved,
    record_repair_pack_verification_failure,
)

router = APIRouter(
    prefix="/admin/data-flywheel",
    tags=["admin-data-flywheel"],
    dependencies=[Depends(require_admin)],
)

REPAIR_PACK_BASE_DIR = Path("data/repair-packs")


class CreateRepairPackRequest(BaseModel):
    sample_ids: list[str] | None = None
    sample_type: str = SAMPLE_TYPE_SESSION_TURN
    label: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    q: str | None = None
    unannotated_only: bool = False
    fix_target: str | None = None
    fix_target_override: str | None = None
    regression_ready: bool | None = None
    min_priority: int | None = Field(default=None, ge=0, le=100)
    limit: int = Field(default=5, ge=1, le=100)


class ResolveRepairPackRequest(BaseModel):
    repair_note: str | None = None
    verification_summary: dict[str, Any] | None = None


class VerificationFailureRequest(BaseModel):
    verification_summary: dict[str, Any]


@router.get("/repair-candidates")
def list_admin_data_flywheel_repair_candidates(
    sample_ids: list[str] | None = Query(None),
    sample_type: str = Query(SAMPLE_TYPE_SESSION_TURN),
    label: str | None = Query(None),
    session_id: str | None = Query(None),
    request_id: str | None = Query(None),
    q: str | None = Query(None),
    unannotated_only: bool = Query(False),
    fix_target: str | None = Query(None),
    regression_ready: bool | None = Query(None),
    min_priority: int | None = Query(None, ge=0, le=100),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """列出 Data Flywheel 样本对应的修复候选。"""
    try:
        return list_repair_candidates(
            db,
            farm_id=farm.id,
            sample_ids=sample_ids,
            sample_type=sample_type or SAMPLE_TYPE_SESSION_TURN,
            label=label,
            session_id=session_id,
            request_id=request_id,
            q=q,
            unannotated_only=unannotated_only,
            fix_target=fix_target,
            regression_ready=regression_ready,
            min_priority=min_priority,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/repair-packs")
def create_admin_data_flywheel_repair_pack(
    body: CreateRepairPackRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """从当前筛选或显式样本集合生成 repair pack。"""
    try:
        return create_repair_pack(
            db,
            farm_id=farm.id,
            export_base_dir=REPAIR_PACK_BASE_DIR,
            sample_ids=body.sample_ids,
            sample_type=body.sample_type or SAMPLE_TYPE_SESSION_TURN,
            label=body.label,
            session_id=body.session_id,
            request_id=body.request_id,
            q=body.q,
            unannotated_only=body.unannotated_only,
            fix_target=body.fix_target,
            fix_target_override=body.fix_target_override,
            regression_ready=body.regression_ready,
            min_priority=body.min_priority,
            limit=body.limit,
            created_by=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/repair-packs/{pack_id}")
def get_admin_data_flywheel_repair_pack(
    pack_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """获取 repair pack 元数据。"""
    try:
        return get_repair_pack(db, farm_id=farm.id, pack_id=pack_id)
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/repair-packs/{pack_id}/resolve")
def resolve_admin_data_flywheel_repair_pack(
    pack_id: str,
    body: ResolveRepairPackRequest | None = None,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """标记 repair pack 已修复，并 resolve 关联 open labels。"""
    payload = body or ResolveRepairPackRequest()
    try:
        return mark_repair_pack_resolved(
            db,
            farm_id=farm.id,
            pack_id=pack_id,
            repair_note=payload.repair_note,
            verification_summary=payload.verification_summary,
            resolved_by=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.post("/repair-packs/{pack_id}/verification-failed")
def fail_admin_data_flywheel_repair_pack_verification(
    pack_id: str,
    body: VerificationFailureRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """记录 repair pack 验证失败，不 resolve 关联 labels。"""
    try:
        return record_repair_pack_verification_failure(
            db,
            farm_id=farm.id,
            pack_id=pack_id,
            verification_summary=body.verification_summary,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


def _http_error(exc: ValueError) -> HTTPException:
    if exc.args and isinstance(exc.args[0], dict):
        return HTTPException(status_code=400, detail=exc.args[0])
    code = str(exc)
    status_code = 404 if code == "REPAIR_PACK_NOT_FOUND" else 400
    return HTTPException(status_code=status_code, detail={"code": code})
