"""Admin 数据飞轮问题链 API。"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.modules.auth.dependencies import get_current_user, require_admin
from app.modules.farm.dependencies import get_current_farm
from app.models.farm import Farm
from app.models.user import User
from app.platforms.data_flywheel.review_issue_chain_service import (
    create_review_issue_chain_candidate,
    get_review_issue_chain_detail,
    list_daily_review_inbox,
    run_review_issue_chain_ai_judge,
    save_review_issue_chain_review,
)
from app.platforms.data_flywheel.router import build_data_flywheel_judge_client
from app.platforms.data_flywheel.review_issue_chain_case import (
    build_case_draft_from_review_issue_chain,
)
from app.platforms.data_flywheel.review_issue_chain_repair import (
    create_repair_pack_from_review_issue_chain,
)

router = APIRouter(
    prefix="/admin/data-flywheel",
    tags=["admin-data-flywheel"],
    dependencies=[Depends(require_admin)],
)

REPAIR_PACK_BASE_DIR = Path("data/repair-packs")


class ReviewIssueChainReviewRequest(BaseModel):
    status: str
    context_turn_ids: list[int] | None = None
    result_turn_ids: list[int] | None = None
    final_labels: list[str] | None = None
    root_cause: str | None = None
    expected_behavior: str | None = None
    fix_target: str | None = None
    reviewer_comment: str | None = None
    false_positive_reason: str | None = None
    missing_evidence: list[str] | None = None


class ChainCaseDraftRequest(BaseModel):
    target_type: str = "evaluation_replay"
    chain_payload: dict[str, Any] | None = None


class ReviewIssueChainCandidateRequest(BaseModel):
    trigger_turn_id: int
    context_turn_ids: list[int] | None = None
    result_turn_ids: list[int] | None = None
    severity: str | None = None
    dominant_signal: str | None = None
    suggested_labels: list[str] | None = None
    missing_evidence: list[str] | None = None


@router.get("/daily-review/inbox")
def list_admin_data_flywheel_daily_review_inbox(
    session_id: str | None = Query(None),
    min_risk: float = Query(0.1, ge=0.0, le=1.0),
    severity: str = Query("all", pattern="^(P0|P1|all)$"),
    status: str = Query("all"),
    evidence_status: str = Query("all"),
    dominant_signal: str = Query("all"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """按 session 聚合每日质检风险问题链。"""
    return list_daily_review_inbox(
        db,
        farm_id=farm.id,
        session_id=session_id,
        min_risk=min_risk,
        severity=severity,
        status=status,
        evidence_status_value=evidence_status,
        dominant_signal_value=dominant_signal,
        limit=limit,
        offset=offset,
    )


@router.post("/review-issue-chains/candidates")
def create_admin_data_flywheel_review_issue_chain_candidate(
    body: ReviewIssueChainCandidateRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """从高级搜索 raw turn 创建每日质检候选链。"""
    try:
        return create_review_issue_chain_candidate(
            db,
            farm_id=farm.id,
            trigger_turn_id=body.trigger_turn_id,
            context_turn_ids=body.context_turn_ids,
            result_turn_ids=body.result_turn_ids,
            severity=body.severity,
            dominant_signal=body.dominant_signal,
            missing_evidence=body.missing_evidence,
            reviewer_id=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc) from exc


@router.get("/review-issue-chains/{chain_id}")
def get_admin_data_flywheel_review_issue_chain(
    chain_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """获取 ReviewIssueChain 详情。"""
    try:
        return get_review_issue_chain_detail(db, farm_id=farm.id, chain_id=chain_id)
    except ValueError as exc:
        raise _http_error(exc, chain_id=chain_id) from exc


@router.post("/review-issue-chains/{chain_id}/review")
def save_admin_data_flywheel_review_issue_chain_review(
    chain_id: str,
    body: ReviewIssueChainReviewRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """保存 ReviewIssueChain 人工审核结论。"""
    try:
        return save_review_issue_chain_review(
            db,
            farm_id=farm.id,
            chain_id=chain_id,
            status=body.status,
            context_turn_ids=body.context_turn_ids,
            result_turn_ids=body.result_turn_ids,
            final_labels=body.final_labels,
            root_cause=body.root_cause,
            expected_behavior=body.expected_behavior,
            fix_target=body.fix_target,
            reviewer_comment=body.reviewer_comment,
            false_positive_reason=body.false_positive_reason,
            missing_evidence=body.missing_evidence,
            reviewer_id=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc, chain_id=chain_id, status=body.status) from exc


@router.post("/review-issue-chains/{chain_id}/ai-judge")
def run_admin_data_flywheel_review_issue_chain_ai_judge(
    chain_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
) -> dict[str, Any]:
    """手动运行 ReviewIssueChain 级 AI 预判。"""
    try:
        return run_review_issue_chain_ai_judge(
            db,
            farm_id=farm.id,
            chain_id=chain_id,
            judge_client=build_data_flywheel_judge_client(),
        )
    except ValueError as exc:
        raise _http_error(exc, chain_id=chain_id) from exc
    except Exception as exc:
        raise _ai_judge_upstream_error(chain_id=chain_id) from exc


@router.post("/review-issue-chains/{chain_id}/case-draft")
def build_admin_data_flywheel_review_issue_chain_case_draft(
    chain_id: str,
    body: ChainCaseDraftRequest,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """从 ReviewIssueChain 生成评测用例草稿。"""
    try:
        return build_case_draft_from_review_issue_chain(
            db,
            farm_id=farm.id,
            chain_id=chain_id,
            target_type=body.target_type,
            created_by=user.id,
            chain_payload=body.chain_payload,
        )
    except ValueError as exc:
        raise _http_error(exc, chain_id=chain_id) from exc


@router.post("/review-issue-chains/{chain_id}/repair-pack")
def create_admin_data_flywheel_review_issue_chain_repair_pack(
    chain_id: str,
    db: Session = Depends(get_db),
    farm: Farm = Depends(get_current_farm),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """从 ReviewIssueChain 导出 repair pack。"""
    try:
        return create_repair_pack_from_review_issue_chain(
            db,
            farm_id=farm.id,
            chain_id=chain_id,
            export_base_dir=REPAIR_PACK_BASE_DIR,
            created_by=user.id,
        )
    except ValueError as exc:
        raise _http_error(exc, chain_id=chain_id) from exc


def _http_error(
    exc: ValueError, *, chain_id: str | None = None, status: str | None = None
) -> HTTPException:
    if exc.args and isinstance(exc.args[0], dict):
        payload = dict(exc.args[0])
    else:
        payload = {"code": str(exc)}
    if chain_id is not None:
        payload["chain_id"] = chain_id
    if status is not None:
        payload["status"] = status
    code = str(payload.get("code") or "")
    status_code = 404 if code in {"CHAIN_NOT_FOUND", "REPAIR_PACK_NOT_FOUND"} else 400
    return HTTPException(status_code=status_code, detail=payload)


def _ai_judge_upstream_error(*, chain_id: str) -> HTTPException:
    return HTTPException(
        status_code=502,
        detail={
            "code": "AI_JUDGE_UPSTREAM_ERROR",
            "chain_id": chain_id,
            "message": "AI 预判服务暂不可用，请稍后重试。",
        },
    )
