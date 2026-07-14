"""Pending action 确认上下文和展示文案。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.infra.pending_action_labels import (
    _SKILL_DISPLAY,
    _SKILL_EMOJI,
    _SKILL_PARAM_FORMAT,
)

_CREATE_WORK_ORDER = "create_work_order"
_WORK_ORDER_ALIAS_TO_OPERATION = {
    "create_operation_work_order": _CREATE_WORK_ORDER,
    "get_operation_work_orders": "query_work_orders",
    "update_operation_work_order": "update_work_order",
}


def _work_order_operation(skill_name: str, params: dict) -> str | None:
    return str(params.get("operation") or "") or _WORK_ORDER_ALIAS_TO_OPERATION.get(
        skill_name
    )


def build_confirmation_context(
    skill_name: str,
    params: dict,
    original_input: str = "",
) -> dict:
    """构建结构化确认上下文。"""
    if _work_order_operation(skill_name, params) == _CREATE_WORK_ORDER:
        return _build_create_work_order_context(skill_name, params, original_input)

    if skill_name == "update_crop_cycle" or (
        skill_name == "manage_crop_cycle"
        and params.get("operation") in {"update_cycle", "update_stage"}
    ):
        return {
            "skill_name": skill_name,
            "original_input": original_input,
            "target": {
                "type": "crop_cycle",
                "id": params.get("cycle_id"),
                "name": params.get("cycle_name") or params.get("crop_name") or "茬口",
            },
            "changes": [
                {
                    "field": "start_date",
                    "label": "开始日期",
                    "old": params.get("old_start_date"),
                    "new": params.get("start_date"),
                }
            ],
            "inferred_fields": {
                "crop_name": params.get("crop_name"),
                "start_date": params.get("start_date"),
            },
            "risk_notes": [],
            "editable_fields": ["start_date", "season", "batch_note"],
        }

    if skill_name == "settle_labor_payment":
        worker = params.get("worker") or params.get("worker_name")
        scope = params.get("scope")
        return {
            "skill_name": skill_name,
            "original_input": original_input,
            "target": {
                "type": "labor_payment",
                "scope": scope,
                "worker": worker,
                "work_order_id": params.get("work_order_id"),
                "cycle_id": params.get("cycle_id"),
            },
            "changes": [
                {
                    "field": "amount",
                    "label": "结算金额",
                    "old": None,
                    "new": params.get("amount") or "全额结清",
                }
            ],
            "inferred_fields": {
                "scope": scope,
                "worker": worker,
                "affected_entries": params.get("affected_entries"),
            },
            "risk_notes": ["确认后会增加人工已付金额。"],
            "editable_fields": [
                "worker",
                "amount",
                "cycle_id",
                "work_order_id",
                "start_date",
                "end_date",
            ],
        }

    if skill_name == "manage_workers":
        action = params.get("action") or "create"
        return {
            "skill_name": skill_name,
            "original_input": original_input,
            "target": {
                "type": "worker",
                "action": action,
                "id": params.get("worker_id"),
                "name": params.get("name"),
            },
            "changes": [
                {"field": key, "old": None, "new": value}
                for key, value in params.items()
            ],
            "inferred_fields": {},
            "risk_notes": ["停用工人会隐藏当前列表，但保留历史用工和账务记录。"],
            "editable_fields": [
                "action",
                "worker_id",
                "name",
                "phone",
                "default_pay_type",
                "default_unit_price",
                "note",
                "status",
            ],
        }

    if skill_name == "manage_wages":
        action = params.get("action") or "save"
        return {
            "skill_name": skill_name,
            "original_input": original_input,
            "target": {
                "type": "wage",
                "action": action,
                "labor_entry_id": params.get("labor_entry_id"),
                "worker": params.get("worker_name") or params.get("worker_id"),
            },
            "changes": [
                {"field": key, "old": None, "new": value}
                for key, value in params.items()
            ],
            "inferred_fields": {
                "client_request_id": params.get("client_request_id"),
            },
            "risk_notes": ["确认后会创建或更新工资记录，并同步人工成本账单。"],
            "editable_fields": [
                "action",
                "labor_entry_id",
                "cycle_id",
                "operation_type",
                "worker_id",
                "worker_name",
                "pay_type",
                "quantity",
                "unit_price",
                "paid_amount",
                "work_date",
                "note",
            ],
        }

    if skill_name in {
        "manage_cost",
        "delete_cost_record",
        "manage_cost_categories",
        "manage_planting_units",
        "manage_crop_templates",
        "manage_crop_cycle",
        "manage_farm_logs",
        "delete_crop_cycle",
        "manage_user_settings",
    }:
        return _build_generic_business_context(skill_name, params, original_input)

    return {
        "skill_name": skill_name,
        "original_input": original_input,
        "target": {
            "type": skill_name,
            "name": _SKILL_DISPLAY.get(skill_name, skill_name),
        },
        "changes": [
            {"field": key, "old": None, "new": value} for key, value in params.items()
        ],
        "inferred_fields": {},
        "risk_notes": [],
        "editable_fields": list(params.keys()),
    }


def build_confirm_message(
    skill_name: str, params: dict, original_input: str = ""
) -> str:
    context = build_confirmation_context(skill_name, params, original_input)
    if _work_order_operation(skill_name, params) == _CREATE_WORK_ORDER:
        target = context["target"]
        labor = context["labor"]
        lines = [
            f"🧑‍🌾 确认创建农事作业单：{target['operation_type']}",
            f"日期：{target.get('operation_date') or '今天'}",
        ]
        units = context["scope"].get("units") or []
        if units:
            lines.append(f"范围：{'、'.join(units)}")
        if labor.get("workers"):
            lines.append(f"人工：{'、'.join(labor['workers'])}")
            if labor.get("quantity"):
                lines.append(f"数量：{labor['quantity']}")
            if labor.get("unit_price"):
                source_suffix = ""
                if labor.get("unit_price_source") == "worker_default":
                    source_suffix = "（来自工人默认工资）"
                lines.append(f"单价：{labor['unit_price']}元{source_suffix}")
            lines.append(
                f"付款：应付{labor['payable_amount']}元，"
                f"已付{labor['paid_amount']}元，"
                f"未付{labor['unpaid_amount']}元"
            )
        if original_input:
            lines.append(f"理解：您说的是「{original_input}」")
        lines.append("确认吗？")
        return "\n".join(lines)

    if skill_name == "update_crop_cycle" or (
        skill_name == "manage_crop_cycle"
        and params.get("operation") in {"update_cycle", "update_stage"}
    ):
        target = context["target"]["name"]
        change = context["changes"][0]
        lines = [
            f"🔄 确认修改茬口：{target}",
            f"{change['label']}：{change['old']} → {change['new']}",
        ]
        if original_input:
            lines.append(f"理解：您说的是「{original_input}」")
        lines.append("确认吗？")
        return "\n".join(lines)

    if skill_name == "manage_workers":
        target = context["target"]
        action_label = {
            "create": "创建工人",
            "update": "更新工人",
            "deactivate": "停用工人",
            "restore": "恢复工人",
        }.get(target.get("action"), "管理工人")
        name = target.get("name") or f"工人#{target.get('id')}"
        lines = [f"👷 确认{action_label}：{name}"]
        price = params.get("default_unit_price")
        if price is not None:
            lines.append(f"默认单价：{price}元")
        if target.get("action") == "deactivate":
            lines.append("说明：这是停用/离职，不会物理删除历史用工和账务。")
        if original_input:
            lines.append(f"理解：您说的是「{original_input}」")
        lines.append("确认吗？")
        return "\n".join(lines)

    if skill_name == "manage_wages":
        target = context["target"]
        action_label = "更新工资" if target.get("action") == "update" else "保存工资"
        worker = target.get("worker") or "工人"
        lines = [f"💳 确认{action_label}：{worker}"]
        if params.get("labor_entry_id"):
            lines.append(f"工资记录：#{params['labor_entry_id']}")
        if params.get("work_date"):
            lines.append(f"日期：{params['work_date']}")
        if params.get("operation_type"):
            lines.append(f"作业：{params['operation_type']}")
        if params.get("unit_price") is not None:
            lines.append(f"单价：{params['unit_price']}元")
        if params.get("quantity") is not None:
            lines.append(f"数量：{params['quantity']}")
        if params.get("paid_amount") is not None:
            lines.append(f"已付：{params['paid_amount']}元")
        if original_input:
            lines.append(f"理解：您说的是「{original_input}」")
        lines.append("确认吗？")
        return "\n".join(lines)

    if skill_name == "settle_labor_payment":
        target = context["target"]
        if target.get("scope") == "all_unpaid_labor":
            target_text = "全部未付人工"
        elif target.get("worker"):
            target_text = str(target["worker"])
        elif target.get("work_order_id"):
            target_text = f"作业单#{target['work_order_id']}"
        elif target.get("cycle_id"):
            target_text = f"茬口#{target['cycle_id']}"
        else:
            target_text = "待确认人工范围"
        amount = params.get("amount") or "全额结清"
        lines = [
            f"💳 确认结算人工：{target_text}",
            f"结算金额：{amount}",
        ]
        if original_input:
            lines.append(f"理解：您说的是「{original_input}」")
        lines.append("确认吗？")
        return "\n".join(lines)

    if skill_name in {
        "manage_cost",
        "delete_cost_record",
        "manage_cost_categories",
        "manage_planting_units",
        "manage_crop_templates",
        "manage_crop_cycle",
        "manage_farm_logs",
        "delete_crop_cycle",
        "manage_user_settings",
    }:
        return _build_generic_business_confirm_message(
            skill_name, params, original_input, context
        )

    emoji = _SKILL_EMOJI.get(skill_name, "❓")
    action = _SKILL_DISPLAY.get(skill_name, skill_name)

    param_keys = _SKILL_PARAM_FORMAT.get(skill_name, list(params.keys()))
    parts = []
    for k in param_keys:
        v = params.get(k)
        if v is not None:
            if k == "amount":
                parts.append(f"{v}元")
            elif k == "record_type":
                label = "收入" if v == "income" else "支出"
                parts.append(label)
            else:
                parts.append(str(v))

    detail = " ".join(parts) if parts else ""

    lines = []
    lines.append(f"{emoji} 确认{action}：{detail}")

    if original_input:
        lines.append(f"理解：您说的是「{original_input}」")

    lines.append("确认吗？")
    return "\n".join(lines)


def build_plan_confirm_message(steps) -> str:
    """构建多步骤 pending plan 的批量确认文案。"""
    lines = [f"请确认将执行 {len(steps)} 步（共 {len(steps)} 个步骤）："]
    for index, step in enumerate(steps, start=1):
        tool_name = getattr(step, "tool_name", "")
        params = getattr(step, "params", {}) or {}
        lines.append(f"{index}. {_format_plan_step(tool_name, params)}")
    lines.append("确认执行吗？")
    return "\n".join(lines)


def _format_plan_step(tool_name: str, params: dict) -> str:
    if tool_name == "manage_workers":
        action = params.get("action") or "create"
        name = params.get("name") or "工人"
        if action == "create":
            return f"创建工人：{name}"
        return f"管理工人：{name}"

    if _work_order_operation(tool_name, params) == _CREATE_WORK_ORDER:
        operation_type = params.get("operation_type") or "农事"
        units = _split_names(params.get("unit_names"))
        scope = f"（{'、'.join(units)}）" if units else ""
        return f"创建{operation_type}作业单{scope}"

    action = _SKILL_DISPLAY.get(tool_name, tool_name)
    return str(action)


def _build_create_work_order_context(
    skill_name: str,
    params: dict,
    original_input: str,
) -> dict:
    workers = _split_names(params.get("workers"))
    unit_price = _to_decimal(params.get("unit_price")) or Decimal("0")
    quantity = _to_decimal(params.get("quantity")) or Decimal("1")
    paid_amount = _to_decimal(params.get("paid_amount")) or Decimal("0")
    payable = _to_decimal(params.get("payable_amount"))
    unit_payable = payable if payable is not None else unit_price * quantity
    total_payable = unit_payable * len(workers)
    total_paid = paid_amount
    total_unpaid = max(total_payable - total_paid, Decimal("0"))
    unit_price_source = params.get("unit_price_source")
    return {
        "skill_name": skill_name,
        "original_input": original_input,
        "target": {
            "type": "operation_work_order",
            "operation_type": params.get("operation_type"),
            "operation_date": params.get("operation_date"),
            "cycle_id": params.get("cycle_id"),
        },
        "scope": {
            "scope_type": "unit" if params.get("unit_names") else "cycle",
            "units": _split_names(params.get("unit_names")),
        },
        "labor": {
            "workers": workers,
            "quantity": _decimal_text(quantity) if workers else None,
            "unit_price": _decimal_text(unit_price) if workers else None,
            "unit_price_source": unit_price_source,
            "payable_amount": _money_text(total_payable),
            "paid_amount": _money_text(total_paid),
            "unpaid_amount": _money_text(total_unpaid),
            "paid_worker": params.get("paid_worker"),
        },
        "changes": [
            {"field": key, "old": None, "new": value} for key, value in params.items()
        ],
        "inferred_fields": {
            "operation_date": params.get("operation_date"),
            "cycle_id": params.get("cycle_id"),
            "paid_worker": params.get("paid_worker"),
            "unit_price_source": unit_price_source,
        },
        "risk_notes": ["确认后会创建作业单和人工成本。"],
        "editable_fields": [
            "operation_type",
            "operation_date",
            "cycle_id",
            "unit_names",
            "workers",
            "unit_price",
            "payable_amount",
            "paid_worker",
            "paid_amount",
            "note",
        ],
    }


def _build_generic_business_context(
    skill_name: str,
    params: dict,
    original_input: str,
) -> dict:
    risk_notes = []
    if skill_name == "delete_crop_cycle" or (
        skill_name == "manage_crop_cycle" and params.get("operation") == "delete_cycle"
    ):
        risk_notes.append("删除茬口会级联删除阶段、农事日志、成本记录和种植单元。")
    elif skill_name == "manage_cost" and params.get("operation") == "delete_record":
        risk_notes.append("确认后会软删除该账务记录，并影响统计结果。")
    elif (
        skill_name == "manage_crop_templates"
        and params.get("operation") in (None, "manage_template")
        and params.get("action") == "delete"
    ):
        risk_notes.append("删除模板会级联删除相关茬口、农事日志和成本记录。")
    elif skill_name == "delete_cost_record":
        risk_notes.append("确认后会软删除该账务记录，并影响统计结果。")
    elif skill_name == "manage_farm_logs" and params.get("action") == "delete":
        risk_notes.append("删除农事日志会影响历史农事记录。")
    elif skill_name == "manage_planting_units" and params.get("action") == "delete":
        risk_notes.append("删除种植单元会移除其作业范围关联。")
    elif skill_name == "manage_user_settings":
        risk_notes.append("设置只会修改当前登录用户。")

    return {
        "skill_name": skill_name,
        "original_input": original_input,
        "target": {
            "type": skill_name,
            "action": params.get("action"),
            "name": _SKILL_DISPLAY.get(skill_name, skill_name),
            "id": (
                params.get("record_id")
                or params.get("category_id")
                or params.get("unit_id")
                or params.get("template_id")
                or params.get("log_id")
                or params.get("cycle_id")
            ),
        },
        "changes": [
            {"field": key, "old": None, "new": value} for key, value in params.items()
        ],
        "inferred_fields": {},
        "risk_notes": risk_notes,
        "editable_fields": list(params.keys()),
    }


def _build_generic_business_confirm_message(
    skill_name: str,
    params: dict,
    original_input: str,
    context: dict,
) -> str:
    emoji = _SKILL_EMOJI.get(skill_name, "❓")
    action = _SKILL_DISPLAY.get(skill_name, skill_name)
    action_value = params.get("action")
    if skill_name == "manage_crop_templates":
        action = "作物模板"
        action_value = _crop_template_action_value(params)
    action_label = {
        "create": "创建",
        "update": "更新",
        "delete": "删除",
    }.get(action_value, "")
    label = f"{action_label}{action}" if action_label else action
    detail_keys = _SKILL_PARAM_FORMAT.get(skill_name, list(params.keys()))
    details = []
    for key in detail_keys:
        value = params.get(key)
        if value is not None:
            details.append(str(value))
    lines = [f"{emoji} 确认{label}：{' '.join(details)}".rstrip()]
    for note in context.get("risk_notes") or []:
        lines.append(f"说明：{note}")
    if original_input:
        lines.append(f"理解：您说的是「{original_input}」")
    lines.append("确认吗？")
    return "\n".join(lines)


def _crop_template_action_value(params: dict) -> str | None:
    if params.get("operation") == "create_template":
        return "create"
    if params.get("operation") == "manage_template":
        return params.get("action")
    return params.get("action")


def _split_names(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [
        part.strip()
        for part in str(value).replace("，", ",").split(",")
        if part.strip()
    ]


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _money_text(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return str(normalized)


__all__ = [
    "build_confirmation_context",
    "build_confirm_message",
    "build_plan_confirm_message",
]
