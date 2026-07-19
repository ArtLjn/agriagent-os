"""写操作确认机制 — pending action 存储与意图检测。"""

import logging
import re
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime

from langchain_core.messages import ToolMessage

from app.shared.database import SessionLocal
from app.infra.pending_action_presenter import (
    build_confirm_message,
    build_confirmation_context,
    build_plan_confirm_message,
)
from app.agent import pending_plan_service

_CONFIRM_PATTERNS = re.compile(r"(确认|好的|是的|没问题|对)")
_CANCEL_PATTERNS = re.compile(r"(算了|取消|不要了|不需要了)")

WRITE_SKILLS = frozenset(
    {
        "create_cost_record",
        "create_crop_cycle",
        "manage_crop_cycle",
        "create_crop_template",
        "manage_work_orders",
        "create_operation_work_order",
        "settle_debt",
        "manage_labor_payment",
        "update_crop_cycle",
        "update_operation_work_order",
        "manage_workers",
        "delete_cost_record",
        "manage_cost_categories",
        "manage_planting_units",
        "manage_crop_templates",
        "manage_farm_logs",
        "delete_crop_cycle",
        "manage_user_settings",
    }
)

# 写操作 skill -> 需要失效的 skill 缓存组
_CACHE_INVALIDATION_MAP: dict[str, list[str]] = {
    "create_cost_record": ["cost_analytics", "cost_summary", "get_farm_status"],
    "create_crop_cycle": ["crop_cycle", "get_farm_status"],
    "manage_crop_cycle": [
        "crop_cycle",
        "farm_logs",
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ],
    "create_crop_template": [],
    "log_farm_activity": ["farm_logs", "get_farm_status"],
    "manage_work_orders": [
        "farm_logs",
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ],
    "create_operation_work_order": [
        "farm_logs",
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ],
    "settle_debt": ["cost_analytics", "cost_summary", "get_farm_status"],
    "manage_labor_payment": ["cost_analytics", "cost_summary", "get_farm_status"],
    "update_crop_cycle": ["crop_cycle", "get_farm_status"],
    "update_crop_stage": ["crop_cycle", "get_farm_status"],
    "update_operation_work_order": [
        "farm_logs",
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ],
    "manage_workers": ["get_farm_status"],
    "delete_cost_record": ["cost_analytics", "cost_summary", "get_farm_status"],
    "manage_cost_categories": ["cost_analytics", "cost_summary", "get_farm_status"],
    "manage_planting_units": ["get_farm_status"],
    "manage_crop_templates": [
        "crop_cycle",
        "farm_logs",
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ],
    "manage_farm_logs": ["farm_logs", "get_farm_status"],
    "delete_crop_cycle": [
        "crop_cycle",
        "farm_logs",
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ],
    "manage_user_settings": ["get_farm_status"],
}


def get_cache_groups_for_skill(skill_name: str) -> list[str]:
    """返回写操作 skill 执行后需要清除的 skill 缓存组。"""
    return _CACHE_INVALIDATION_MAP.get(skill_name, [])


_TIMEOUT_SECONDS = 300  # 5分钟超时

logger = logging.getLogger(__name__)


@dataclass
class PendingAction:
    """待确认的操作。"""

    action_id: str
    skill_name: str
    params: dict
    created_at: float
    farm_id: int
    original_input: str = ""
    confirmation_context: dict | None = None
    follow_up_skill_name: str | None = None
    follow_up_params: dict | None = None
    follow_up_original_input: str = ""
    session_id: str | None = None


@dataclass
class PendingPlanStep:
    """Pending Plan 中等待确认或执行的步骤。"""

    step_id: str
    step_index: int
    tool_name: str
    params: dict
    depends_on: list[str]
    confirmation_state: str = "pending"
    execution_status: str = "pending"
    result_payload: dict | None = None
    error_payload: dict | None = None


@dataclass
class PendingPlan:
    """待确认的多步骤计划。"""

    plan_id: str
    farm_id: int
    session_id: str | None
    status: str
    current_step_index: int
    raw_user_input: str
    router_decision: dict
    steps: list[PendingPlanStep]
    created_at: float
    expires_at: float | None = None


# 内存字典：(farm_id, session_id) -> PendingAction
_pending: dict[tuple[int, str | None], PendingAction] = {}
_pending_plans: dict[tuple[int, str | None], PendingPlan] = {}


def _pending_key(farm_id: int, session_id: str | None = None) -> tuple[int, str | None]:
    return farm_id, session_id or None


def store_pending(
    farm_id: int,
    skill_name: str,
    params: dict,
    original_input: str = "",
    confirmation_context: dict | None = None,
    follow_up_skill_name: str | None = None,
    follow_up_params: dict | None = None,
    follow_up_original_input: str = "",
    session_id: str | None = None,
) -> str:
    """存储 pending action，返回 action_id。"""
    action_id = uuid.uuid4().hex
    _pending[_pending_key(farm_id, session_id)] = PendingAction(
        action_id=action_id,
        skill_name=skill_name,
        params=params,
        created_at=time.time(),
        farm_id=farm_id,
        original_input=original_input,
        confirmation_context=confirmation_context,
        follow_up_skill_name=follow_up_skill_name,
        follow_up_params=follow_up_params,
        follow_up_original_input=follow_up_original_input,
        session_id=session_id,
    )
    logger.info(
        "Pending action 已存储 | farm_id=%d | action_id=%s | skill=%s",
        farm_id,
        action_id,
        skill_name,
    )
    return action_id


def store_pending_plan(
    farm_id: int,
    session_id: str | None,
    raw_user_input: str,
    router_decision: dict,
    steps: list[dict | PendingPlanStep],
) -> str:
    """存储 pending plan，返回 plan_id。"""
    pending_steps = [
        _coerce_pending_plan_step(step, index) for index, step in enumerate(steps)
    ]
    db = SessionLocal()
    try:
        db_plan = pending_plan_service.create_pending_plan(
            db,
            farm_id=farm_id,
            session_id=session_id,
            raw_user_input=raw_user_input,
            router_decision=deepcopy(router_decision),
            steps=[
                {
                    "skill_name": step.tool_name,
                    "params": deepcopy(step.params),
                    "requires_confirmation": True,
                    "confirmation_text": None,
                    "step_id": step.step_id,
                    "depends_on": deepcopy(step.depends_on),
                }
                for step in pending_steps
            ],
            ttl_seconds=_TIMEOUT_SECONDS,
        )
        plan_id = db_plan.plan_id
    finally:
        db.close()

    _pending_plans[_pending_key(farm_id, session_id)] = PendingPlan(
        plan_id=plan_id,
        farm_id=farm_id,
        session_id=session_id,
        status="pending",
        current_step_index=0,
        raw_user_input=raw_user_input,
        router_decision=deepcopy(router_decision),
        steps=pending_steps,
        created_at=time.time(),
        expires_at=time.time() + _TIMEOUT_SECONDS,
    )
    logger.info(
        "Pending plan 已存储 | farm_id=%d | plan_id=%s | steps=%d",
        farm_id,
        plan_id,
        len(pending_steps),
    )
    return plan_id


def _coerce_pending_plan_step(
    step: dict | PendingPlanStep,
    index: int,
) -> PendingPlanStep:
    """兼容 dict 和 PendingPlanStep 两种 pending plan step 输入。"""
    if isinstance(step, PendingPlanStep):
        return PendingPlanStep(
            step_id=step.step_id,
            step_index=index,
            tool_name=step.tool_name,
            params=deepcopy(step.params),
            depends_on=deepcopy(step.depends_on),
            confirmation_state=step.confirmation_state,
            execution_status=step.execution_status,
            result_payload=deepcopy(step.result_payload),
            error_payload=deepcopy(step.error_payload),
        )

    return PendingPlanStep(
        step_id=str(step.get("step_id") or f"step-{index + 1}"),
        step_index=index,
        tool_name=str(step["tool_name"]),
        params=deepcopy(step.get("params") or {}),
        depends_on=deepcopy(step.get("depends_on") or []),
        confirmation_state=str(step.get("confirmation_state") or "pending"),
        execution_status=str(step.get("execution_status") or "pending"),
        result_payload=deepcopy(step.get("result_payload")),
        error_payload=deepcopy(step.get("error_payload")),
    )


def get_pending(farm_id: int, session_id: str | None = None) -> PendingAction | None:
    """获取 pending action，超时则删除返回 None。"""
    key = _pending_key(farm_id, session_id)
    action = _pending.get(key)
    if action is None:
        return None
    if time.time() - action.created_at > _TIMEOUT_SECONDS:
        logger.warning(
            "Pending action 已超时 | farm_id=%d | skill=%s",
            farm_id,
            action.skill_name,
        )
        del _pending[key]
        return None
    logger.debug(
        "Pending action 获取 | farm_id=%d | skill=%s",
        farm_id,
        action.skill_name,
    )
    return action


def get_pending_plan(farm_id: int, session_id: str | None = None) -> PendingPlan | None:
    """获取 pending plan，超时则删除返回 None。"""
    key = _pending_key(farm_id, session_id)
    plan = _pending_plans.get(key)
    if plan is None:
        plan = _load_pending_plan_from_db(farm_id, session_id)
        if plan is None:
            return None
        _pending_plans[key] = plan
    if plan.expires_at is not None and time.time() > plan.expires_at:
        logger.warning(
            "Pending plan 已超时 | farm_id=%d | plan_id=%s",
            farm_id,
            plan.plan_id,
        )
        _expire_pending_plan_in_db(farm_id, session_id)
        _pending_plans.pop(key, None)
        return None
    logger.debug(
        "Pending plan 获取 | farm_id=%d | plan_id=%s",
        farm_id,
        plan.plan_id,
    )
    return plan


def remove_pending(farm_id: int, session_id: str | None = None) -> None:
    """删除 pending action。"""
    if session_id is None:
        for key in [key for key in _pending if key[0] == farm_id]:
            _pending.pop(key, None)
        for key in [key for key in _pending_plans if key[0] == farm_id]:
            _pending_plans.pop(key, None)
        _cancel_pending_plan_in_db(farm_id, session_id=None)
    else:
        _pending.pop(_pending_key(farm_id, session_id), None)
        _pending_plans.pop(_pending_key(farm_id, session_id), None)
        _cancel_pending_plan_in_db(farm_id, session_id=session_id)
    logger.debug("Pending action 已删除 | farm_id=%d", farm_id)


def _load_pending_plan_from_db(
    farm_id: int,
    session_id: str | None,
) -> PendingPlan | None:
    db = SessionLocal()
    try:
        db_plan = pending_plan_service.get_active_plan(
            db,
            farm_id=farm_id,
            session_id=session_id,
        )
        if db_plan is None:
            return None
        return _db_plan_to_runtime_plan(db_plan)
    finally:
        db.close()


def _db_plan_to_runtime_plan(db_plan) -> PendingPlan:
    created_at = _datetime_to_timestamp(getattr(db_plan, "created_at", None))
    expires_at = _datetime_to_timestamp(getattr(db_plan, "expires_at", None))
    return PendingPlan(
        plan_id=db_plan.plan_id,
        farm_id=db_plan.farm_id,
        session_id=db_plan.session_id,
        status=db_plan.status,
        current_step_index=db_plan.current_step_index,
        raw_user_input=db_plan.raw_user_input or "",
        router_decision=deepcopy(
            db_plan.router_decision_json
            or getattr(db_plan, "router_decision", None)
            or {}
        ),
        steps=[
            PendingPlanStep(
                step_id=step.step_id or f"step-{step.step_index + 1}",
                step_index=step.step_index,
                tool_name=step.skill_name or step.tool_name,
                params=deepcopy(step.params_json or step.params or {}),
                depends_on=deepcopy(step.depends_on or []),
                confirmation_state="pending" if step.requires_confirmation else "none",
                execution_status=step.status,
                result_payload=deepcopy(step.result_json or step.result_payload),
                error_payload=(
                    {"error": step.error_message}
                    if step.error_message
                    else deepcopy(step.error_payload)
                ),
            )
            for step in db_plan.steps
        ],
        created_at=created_at,
        expires_at=expires_at,
    )


def _datetime_to_timestamp(value) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    return time.time()


def _cancel_pending_plan_in_db(farm_id: int, session_id: str | None) -> None:
    db = SessionLocal()
    try:
        if session_id is None:
            plans = (
                db.query(pending_plan_service.AgentPendingPlan)
                .filter(
                    pending_plan_service.AgentPendingPlan.farm_id == farm_id,
                    pending_plan_service.AgentPendingPlan.status.in_(
                        pending_plan_service._ACTIVE_STATUSES
                    ),
                )
                .all()
            )
            for plan in plans:
                plan.status = "cancelled"
                for step in plan.steps:
                    if step.status == "pending":
                        step.status = "cancelled"
            db.commit()
        else:
            pending_plan_service.cancel_active_plan(
                db,
                farm_id=farm_id,
                session_id=session_id,
            )
    finally:
        db.close()


def _expire_pending_plan_in_db(farm_id: int, session_id: str | None) -> None:
    db = SessionLocal()
    try:
        plan = pending_plan_service.get_active_plan(
            db,
            farm_id=farm_id,
            session_id=session_id,
            now=datetime.fromtimestamp(time.time()),
        )
        if plan is not None:
            plan.status = "expired"
            for step in plan.steps:
                if step.status == "pending":
                    step.status = "expired"
            db.commit()
    finally:
        db.close()


def is_write_skill(skill_name: str) -> bool:
    """判断是否为写操作 Skill。"""
    return skill_name in WRITE_SKILLS


def is_write_skill_call(skill_name: str, params: dict | None = None) -> bool:
    """按 registry operation 风险判断当前调用是否需要写确认。"""
    operation_risk = _registry_operation_risk(skill_name, params)
    if operation_risk == "read":
        return False
    if operation_risk in {"write_confirm", "write_high"}:
        return True
    return is_write_skill(skill_name)


def _registry_operation_risk(skill_name: str, params: dict | None = None) -> str | None:
    try:
        from app.skills.registry import load_skill_registry

        registry = load_skill_registry()
    except (OSError, ValueError):
        return None

    alias = registry.resolve_alias(skill_name)
    capability_name = alias.capability if alias is not None else skill_name
    operation_name = _operation_name_from_call(alias, params)
    if operation_name is None:
        return None
    operation = registry.get_operation(capability_name, operation_name)
    return operation.risk if operation is not None else None


def _operation_name_from_call(alias, params: dict | None = None) -> str | None:
    if isinstance(params, dict) and params.get("operation"):
        return str(params["operation"])
    if alias is not None:
        return alias.operation
    return None


PENDING_MARKER = "[PENDING_ACTION]"


def is_pending_tool_message(message) -> bool:
    return isinstance(message, ToolMessage) and PENDING_MARKER in (
        message.content or ""
    )


def detect_user_intent(message: str) -> str:
    """检测用户消息意图：confirm / cancel / modify。

    只有消息整体较短且以确认词/取消词为主导时才判定为确认/取消，
    避免把"是赊账"误判为确认。
    """
    stripped = message.strip()
    if _CANCEL_PATTERNS.search(stripped):
        result = "cancel"
        logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
        return result

    if _CONFIRM_PATTERNS.search(stripped):
        # 确认词匹配后，检查消息长度。短消息（<=10字）才判定为确认，
        # 长消息更可能是修正参数
        confirm_match = _CONFIRM_PATTERNS.search(stripped)
        match_end = confirm_match.end()
        # 确认词后还有较多内容时，视为修正
        remaining = stripped[match_end:].strip()
        if len(stripped) <= 10 and not remaining:
            result = "confirm"
            logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
            return result
        # 如果整条消息就是确认词（如"确认"、"好的"）
        if stripped == confirm_match.group(0):
            result = "confirm"
            logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
            return result
        # 确认词开头且后面内容很短（如"确认一下"、"好的，就这样"）
        if len(remaining) <= 4 and not any(c.isdigit() for c in remaining):
            result = "confirm"
            logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
            return result

    result = "modify"
    logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
    return result


__all__ = [
    "PendingAction",
    "PendingPlan",
    "PendingPlanStep",
    "store_pending",
    "store_pending_plan",
    "get_pending",
    "get_pending_plan",
    "remove_pending",
    "is_write_skill",
    "is_write_skill_call",
    "detect_user_intent",
    "build_confirm_message",
    "build_confirmation_context",
    "build_plan_confirm_message",
    "is_pending_tool_message",
    "PENDING_MARKER",
    "_pending",
    "_pending_plans",
    "WRITE_SKILLS",
    "get_cache_groups_for_skill",
]
