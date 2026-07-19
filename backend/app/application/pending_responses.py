"""Agent pending action/plan response builders."""

from app.infra.pending_actions import get_pending, get_pending_plan
from app.domains.conversation.agent_schemas import (
    PendingActionContext,
    PendingActionResponse,
    PendingPlanResponse,
)


def build_pending_action_response(
    farm_id: int, session_id: str | None = None
) -> PendingActionResponse | None:
    """构造 pending action 响应。"""
    pending = get_pending(farm_id, session_id=session_id)
    if not pending:
        return None
    notes = []
    if pending.original_input:
        notes.append(f"理解：您说的是「{pending.original_input}」")
    display_params = _build_pending_display_params(pending.skill_name, pending.params)
    return PendingActionResponse(
        action_id=pending.action_id,
        skill_name=pending.skill_name,
        params=display_params,
        context=PendingActionContext(
            original_input=pending.original_input,
            extracted_params=display_params,
            notes=notes,
        ),
    )


def build_pending_plan_response(
    farm_id: int, session_id: str | None = None
) -> PendingPlanResponse | None:
    """构造 pending plan 响应。"""
    pending_plan = get_pending_plan(farm_id, session_id=session_id)
    if not pending_plan:
        return None
    return PendingPlanResponse(
        plan_id=pending_plan.plan_id,
        status=pending_plan.status,
        raw_user_input=pending_plan.raw_user_input,
        steps=[
            {
                "step_id": step.step_id,
                "step_index": step.step_index,
                "skill_name": step.tool_name,
                "params": step.params,
                "depends_on": step.depends_on,
                "status": step.execution_status,
            }
            for step in pending_plan.steps
        ],
    )


def _build_pending_display_params(skill_name: str, params: dict) -> dict[str, str]:
    """构造前端展示参数，避免暴露内部字段名。"""
    label_map = {
        "amount": "金额",
        "category": "类别",
        "operation": "操作",
        "record_id": "记录ID",
        "record_type": "类型",
        "crop_name": "作物",
        "season": "季节",
        "start_date": "开始日期",
        "field_name": "地块",
        "operation_type": "操作",
        "counterparty": "对象",
        "stage_name": "阶段",
        "variety": "品种",
    }
    order_map = {
        "manage_cost": [
            "operation",
            "category",
            "amount",
            "record_type",
            "counterparty",
            "record_id",
        ],
        "create_cost_record": ["category", "amount", "record_type"],
        "create_crop_cycle": ["crop_name", "season", "start_date", "field_name"],
        "manage_crop_cycle": [
            "operation",
            "crop_name",
            "cycle_name",
            "cycle_id",
            "season",
            "start_date",
            "current_stage",
            "field_name",
        ],
        "create_crop_template": ["crop_name", "variety"],
        "manage_crop_templates": [
            "operation",
            "action",
            "template_id",
            "crop_name",
            "name",
            "variety",
        ],
        "log_farm_activity": ["operation_type"],
        "manage_farm_logs": ["operation", "action", "log_id", "cycle_id", "operation_type"],
        "settle_debt": ["counterparty", "amount"],
        "update_crop_stage": ["stage_name"],
    }
    ordered_keys = order_map.get(skill_name, list(params.keys()))
    display: dict[str, str] = {}
    for key in ordered_keys:
        value = params.get(key)
        if value is None:
            continue
        label = label_map.get(key, "内容")
        if key == "record_type":
            value = "收入" if value == "income" else "支出"
        elif key == "amount":
            value = f"{value}元"
        display[label] = str(value)
    return display


__all__ = ["build_pending_action_response", "build_pending_plan_response"]
