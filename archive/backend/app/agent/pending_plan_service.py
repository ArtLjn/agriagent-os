"""可恢复 pending plan 服务。"""

import uuid
from datetime import datetime, timedelta
from typing import Any

import logging

from sqlalchemy.orm import Session

from app.agent.pending_plan_models import AgentPendingPlan, AgentPendingPlanStep
from app.observability import increment_counter
from app.shared.config import settings
from app.shared.logging import log_event

_ACTIVE_STATUSES = {"pending", "running"}
logger = logging.getLogger(__name__)


class ConcurrentMutationError(RuntimeError):
    """pending plan 已被其他请求处理。"""


def create_pending_plan(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    raw_user_input: str,
    router_decision: dict[str, Any] | None,
    steps: list[dict[str, Any]],
    ttl_seconds: int,
) -> AgentPendingPlan:
    """创建待确认计划并取消同会话旧计划。"""
    cancel_active_plan(db, farm_id=farm_id, session_id=session_id)
    plan_id = uuid.uuid4().hex
    plan = AgentPendingPlan(
        plan_id=plan_id,
        farm_id=farm_id,
        session_id=session_id,
        status="pending",
        version=0,
        current_step_index=0,
        raw_user_input=raw_user_input,
        router_decision=router_decision,
        router_decision_json=router_decision,
        expires_at=datetime.now() + timedelta(seconds=ttl_seconds),
    )
    db.add(plan)
    for index, item in enumerate(steps):
        db.add(
            AgentPendingPlanStep(
                plan_id=plan_id,
                step_id=item.get("step_id") or f"step-{index + 1}",
                step_index=index,
                tool_name=item["skill_name"],
                skill_name=item["skill_name"],
                params=item.get("params") or {},
                params_json=item.get("params") or {},
                depends_on=item.get("depends_on") or [],
                confirmation_state="pending",
                execution_status="pending",
                status="pending",
                requires_confirmation=item.get("requires_confirmation", True),
                confirmation_text=item.get("confirmation_text"),
            )
        )
    db.commit()
    db.refresh(plan)
    return plan


def get_active_plan(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    now: datetime | None = None,
) -> AgentPendingPlan | None:
    """获取当前会话未过期的 pending plan。"""
    current = now or datetime.now()
    plan = (
        db.query(AgentPendingPlan)
        .with_for_update()
        .filter(
            AgentPendingPlan.farm_id == farm_id,
            AgentPendingPlan.session_id == session_id,
            AgentPendingPlan.status.in_(_ACTIVE_STATUSES),
        )
        .order_by(AgentPendingPlan.created_at.desc(), AgentPendingPlan.id.desc())
        .first()
    )
    if plan is None:
        return None
    if plan.expires_at is not None and plan.expires_at <= current:
        plan.status = "expired"
        for step in plan.steps:
            if step.status == "pending":
                step.status = "expired"
        db.commit()
        return None
    return plan


def confirm_pending_plan(
    db: Session,
    *,
    plan_id: str,
    expected_version: int,
    now: datetime | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> AgentPendingPlan:
    """CAS 确认 pending plan，并在短事务内处理 TTL。"""
    if not settings.pending_plan.concurrency_safety:
        plan = (
            db.query(AgentPendingPlan).filter(AgentPendingPlan.plan_id == plan_id).one()
        )
        plan.status = "running"
        plan.version += 1
        db.commit()
        db.refresh(plan)
        return plan

    current = now or datetime.now()
    plan = (
        db.query(AgentPendingPlan)
        .with_for_update()
        .filter(AgentPendingPlan.plan_id == plan_id)
        .one()
    )
    if plan.status != "pending":
        _record_cas_conflict(
            plan_id=plan_id,
            session_id=session_id,
            user_id=user_id,
            expected_version=expected_version,
            actual_version=plan.version,
            reason="status_not_pending",
        )
        raise ConcurrentMutationError("plan 已被处理或已过期。")
    if plan.expires_at is not None and plan.expires_at <= current:
        plan.status = "expired"
        for step in plan.steps:
            if step.status == "pending":
                step.status = "expired"
        db.commit()
        raise ConcurrentMutationError("确认已超时，请重新发起。")

    affected = (
        db.query(AgentPendingPlan)
        .filter(
            AgentPendingPlan.plan_id == plan_id,
            AgentPendingPlan.version == expected_version,
            AgentPendingPlan.status == "pending",
        )
        .update(
            {
                AgentPendingPlan.status: "running",
                AgentPendingPlan.version: AgentPendingPlan.version + 1,
            },
            synchronize_session=False,
        )
    )
    if affected == 0:
        db.rollback()
        _record_cas_conflict(
            plan_id=plan_id,
            session_id=session_id,
            user_id=user_id,
            expected_version=expected_version,
            actual_version=getattr(plan, "version", None),
            reason="version_mismatch",
        )
        raise ConcurrentMutationError("操作正在处理中，请稍后再试。")
    db.commit()
    plan = db.query(AgentPendingPlan).filter(AgentPendingPlan.plan_id == plan_id).one()
    return plan


def cancel_active_plan(
    db: Session,
    *,
    farm_id: int,
    session_id: str | None,
    expected_version: int | None = None,
) -> bool:
    """取消当前会话未完成计划。"""
    plans = (
        db.query(AgentPendingPlan)
        .filter(
            AgentPendingPlan.farm_id == farm_id,
            AgentPendingPlan.session_id == session_id,
            AgentPendingPlan.status.in_(_ACTIVE_STATUSES),
        )
        .all()
    )
    changed = False
    for plan in plans:
        if expected_version is not None and plan.version != expected_version:
            raise ConcurrentMutationError("操作正在处理中，请稍后再试。")
        plan.status = "cancelled"
        plan.version += 1
        changed = True
        for step in plan.steps:
            if step.status == "pending":
                step.status = "cancelled"
    db.commit()
    return changed


def mark_step_executed(
    db: Session,
    *,
    plan_id: str,
    step_index: int,
    result: dict[str, Any] | None,
) -> AgentPendingPlan:
    """标记步骤已执行，必要时完成整项计划。"""
    plan = db.query(AgentPendingPlan).filter(AgentPendingPlan.plan_id == plan_id).one()
    affected = (
        db.query(AgentPendingPlanStep)
        .filter(
            AgentPendingPlanStep.plan_id == plan_id,
            AgentPendingPlanStep.step_index == step_index,
            AgentPendingPlanStep.status == "pending",
        )
        .update(
            {
                AgentPendingPlanStep.status: "executed",
                AgentPendingPlanStep.execution_status: "executed",
                AgentPendingPlanStep.result_json: result,
                AgentPendingPlanStep.result_payload: result,
            },
            synchronize_session=False,
        )
    )
    if affected == 0:
        db.commit()
        db.refresh(plan)
        return plan
    db.refresh(plan)
    next_pending = next((step for step in plan.steps if step.status == "pending"), None)
    if next_pending is None:
        plan.status = "completed"
    else:
        plan.current_step_index = next_pending.step_index
        plan.status = "pending"
    db.commit()
    db.refresh(plan)
    return plan


def mark_step_failed(
    db: Session,
    *,
    plan_id: str,
    step_index: int,
    error_message: str,
) -> AgentPendingPlan:
    """标记步骤失败并暂停计划。"""
    plan = db.query(AgentPendingPlan).filter(AgentPendingPlan.plan_id == plan_id).one()
    affected = (
        db.query(AgentPendingPlanStep)
        .filter(
            AgentPendingPlanStep.plan_id == plan_id,
            AgentPendingPlanStep.step_index == step_index,
            AgentPendingPlanStep.status == "pending",
        )
        .update(
            {
                AgentPendingPlanStep.status: "failed",
                AgentPendingPlanStep.execution_status: "failed",
                AgentPendingPlanStep.error_message: error_message,
                AgentPendingPlanStep.error_payload: {"error": error_message},
            },
            synchronize_session=False,
        )
    )
    if affected == 0:
        db.commit()
        db.refresh(plan)
        return plan
    plan.status = "failed"
    db.commit()
    db.refresh(plan)
    return plan


def mark_step_compensated(
    db: Session,
    *,
    plan_id: str,
    step_index: int,
    result: dict,
) -> AgentPendingPlan:
    """标记已执行步骤完成补偿。"""
    plan = db.query(AgentPendingPlan).filter(AgentPendingPlan.plan_id == plan_id).one()
    affected = (
        db.query(AgentPendingPlanStep)
        .filter(
            AgentPendingPlanStep.plan_id == plan_id,
            AgentPendingPlanStep.step_index == step_index,
            AgentPendingPlanStep.status == "executed",
        )
        .update(
            {
                AgentPendingPlanStep.status: "compensated",
                AgentPendingPlanStep.execution_status: "compensated",
                AgentPendingPlanStep.result_json: result,
                AgentPendingPlanStep.result_payload: result,
            },
            synchronize_session=False,
        )
    )
    if affected:
        increment_counter("pending_plan_saga_compensate_total", {"result": "success"})
    db.commit()
    db.refresh(plan)
    return plan


def mark_plan_partial_completed(
    db: Session,
    *,
    plan_id: str,
    error_message: str,
    saga_steps: list[dict],
) -> AgentPendingPlan:
    """标记 plan 部分完成，供 UI 和运维显式处理。"""
    plan = db.query(AgentPendingPlan).filter(AgentPendingPlan.plan_id == plan_id).one()
    plan.status = "partial_completed"
    plan.version += 1
    plan.router_decision_json = {
        **(plan.router_decision_json or plan.router_decision or {}),
        "partial_completed_error": error_message,
        "saga_compensate_steps": saga_steps,
    }
    increment_counter("pending_plan_partial_completed_total")
    db.commit()
    db.refresh(plan)
    return plan


def _record_cas_conflict(
    *,
    plan_id: str,
    session_id: str | None,
    user_id: str | None,
    expected_version: int,
    actual_version: int | None,
    reason: str,
) -> None:
    increment_counter("pending_plan_cas_conflict_total")
    log_event(
        logger,
        logging.WARNING,
        "pending_plan.cas_conflict",
        code="PENDING_PLAN_CONFLICT",
        session_id=session_id,
        status="conflict",
        data={
            "plan_id": plan_id,
            "user_id": user_id,
            "expected_version": expected_version,
            "actual_version": actual_version,
            "reason": reason,
        },
    )


def expire_stale_plans(db: Session, *, now: datetime | None = None) -> int:
    """过期所有超时 pending plan。"""
    current = now or datetime.now()
    plans = (
        db.query(AgentPendingPlan)
        .filter(
            AgentPendingPlan.status.in_(_ACTIVE_STATUSES),
            AgentPendingPlan.expires_at.isnot(None),
            AgentPendingPlan.expires_at <= current,
        )
        .all()
    )
    for plan in plans:
        plan.status = "expired"
        for step in plan.steps:
            if step.status == "pending":
                step.status = "expired"
    db.commit()
    return len(plans)
