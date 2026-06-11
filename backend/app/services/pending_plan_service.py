"""可恢复 pending plan 服务。"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.pending_plan import AgentPendingPlan, AgentPendingPlanStep

_ACTIVE_STATUSES = {"pending", "running"}


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
        current_step_index=0,
        raw_user_input=raw_user_input,
        router_decision_json=router_decision,
        expires_at=datetime.now() + timedelta(seconds=ttl_seconds),
    )
    db.add(plan)
    for index, item in enumerate(steps):
        db.add(
            AgentPendingPlanStep(
                plan_id=plan_id,
                step_index=index,
                skill_name=item["skill_name"],
                params_json=item.get("params") or {},
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
        db.commit()
        return None
    return plan


def cancel_active_plan(db: Session, *, farm_id: int, session_id: str | None) -> bool:
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
    for plan in plans:
        plan.status = "cancelled"
        for step in plan.steps:
            if step.status == "pending":
                step.status = "cancelled"
    db.commit()
    return bool(plans)


def mark_step_executed(
    db: Session,
    *,
    plan_id: str,
    step_index: int,
    result: dict[str, Any] | None,
) -> AgentPendingPlan:
    """标记步骤已执行，必要时完成整项计划。"""
    plan = db.query(AgentPendingPlan).filter(AgentPendingPlan.plan_id == plan_id).one()
    target = next(step for step in plan.steps if step.step_index == step_index)
    target.status = "executed"
    target.result_json = result
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
    target = next(step for step in plan.steps if step.step_index == step_index)
    target.status = "failed"
    target.error_message = error_message
    plan.status = "failed"
    db.commit()
    db.refresh(plan)
    return plan


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
