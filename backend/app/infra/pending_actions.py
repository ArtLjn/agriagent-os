"""写操作确认机制 — pending action 存储与意图检测。"""

import logging
import re
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from langchain_core.messages import ToolMessage

_CONFIRM_PATTERNS = re.compile(r"(确认|好的|是的|没问题|对)")
_CANCEL_PATTERNS = re.compile(r"(算了|取消|不要了|不需要了)")

WRITE_SKILLS = frozenset(
    {
        "create_cost_record",
        "create_crop_cycle",
        "create_crop_template",
        "log_farm_activity",
        "create_operation_work_order",
        "settle_debt",
        "settle_labor_payment",
        "update_crop_cycle",
        "update_crop_stage",
        "update_operation_work_order",
    }
)

# 写操作 skill -> 需要失效的 skill 缓存组
_CACHE_INVALIDATION_MAP: dict[str, list[str]] = {
    "create_cost_record": ["cost_analytics", "cost_summary", "get_farm_status"],
    "create_crop_cycle": ["crop_cycle", "get_farm_status"],
    "create_crop_template": [],
    "log_farm_activity": ["farm_logs", "get_farm_status"],
    "create_operation_work_order": [
        "farm_logs",
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ],
    "settle_debt": ["cost_analytics", "cost_summary", "get_farm_status"],
    "settle_labor_payment": ["cost_analytics", "cost_summary", "get_farm_status"],
    "update_crop_cycle": ["crop_cycle", "get_farm_status"],
    "update_crop_stage": ["crop_cycle", "get_farm_status"],
    "update_operation_work_order": [
        "farm_logs",
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ],
}


def get_cache_groups_for_skill(skill_name: str) -> list[str]:
    """返回写操作 skill 执行后需要清除的 skill 缓存组。"""
    return _CACHE_INVALIDATION_MAP.get(skill_name, [])


_SKILL_DISPLAY: dict[str, str] = {
    "create_cost_record": "记账",
    "create_crop_cycle": "创建茬口",
    "create_crop_template": "创建作物模板",
    "log_farm_activity": "记录农事",
    "create_operation_work_order": "创建农事作业单",
    "update_operation_work_order": "更新农事作业单",
    "settle_labor_payment": "结算人工",
    "settle_debt": "还款",
    "update_crop_stage": "更新阶段",
}

_SKILL_EMOJI: dict[str, str] = {
    "create_cost_record": "💰",
    "create_crop_cycle": "🌱",
    "create_crop_template": "📋",
    "log_farm_activity": "📝",
    "create_operation_work_order": "🧑‍🌾",
    "update_operation_work_order": "🧑‍🌾",
    "settle_labor_payment": "💳",
    "settle_debt": "💳",
    "update_crop_stage": "🔄",
}

_SKILL_PARAM_FORMAT: dict[str, list[str]] = {
    "create_cost_record": ["category", "amount", "record_type"],
    "create_crop_cycle": ["crop_name", "season"],
    "create_crop_template": ["crop_name"],
    "log_farm_activity": ["operation_type"],
    "create_operation_work_order": ["operation_type", "operation_date", "cycle_id"],
    "update_operation_work_order": [
        "work_order_id",
        "operation_type",
        "operation_date",
    ],
    "settle_labor_payment": ["worker", "amount", "work_order_id"],
    "settle_debt": ["counterparty", "amount"],
    "update_crop_stage": ["stage_name"],
}

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


# 内存字典：farm_id -> PendingAction
_pending: dict[int, PendingAction] = {}


def store_pending(
    farm_id: int,
    skill_name: str,
    params: dict,
    original_input: str = "",
    confirmation_context: dict | None = None,
    follow_up_skill_name: str | None = None,
    follow_up_params: dict | None = None,
    follow_up_original_input: str = "",
) -> str:
    """存储 pending action，返回 action_id。"""
    action_id = uuid.uuid4().hex
    _pending[farm_id] = PendingAction(
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
    )
    logger.info(
        "Pending action 已存储 | farm_id=%d | action_id=%s | skill=%s",
        farm_id,
        action_id,
        skill_name,
    )
    return action_id


def get_pending(farm_id: int) -> PendingAction | None:
    """获取 pending action，超时则删除返回 None。"""
    action = _pending.get(farm_id)
    if action is None:
        return None
    if time.time() - action.created_at > _TIMEOUT_SECONDS:
        logger.warning(
            "Pending action 已超时 | farm_id=%d | skill=%s",
            farm_id,
            action.skill_name,
        )
        del _pending[farm_id]
        return None
    logger.debug(
        "Pending action 获取 | farm_id=%d | skill=%s",
        farm_id,
        action.skill_name,
    )
    return action


def remove_pending(farm_id: int) -> None:
    """删除 pending action。"""
    _pending.pop(farm_id, None)
    logger.debug("Pending action 已删除 | farm_id=%d", farm_id)


def is_write_skill(skill_name: str) -> bool:
    """判断是否为写操作 Skill。"""
    return skill_name in WRITE_SKILLS


PENDING_MARKER = "[PENDING_ACTION]"


def build_confirmation_context(
    skill_name: str,
    params: dict,
    original_input: str = "",
) -> dict:
    """构建结构化确认上下文。"""
    if skill_name == "create_operation_work_order":
        return _build_create_work_order_context(skill_name, params, original_input)

    if skill_name == "update_crop_cycle":
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
        return {
            "skill_name": skill_name,
            "original_input": original_input,
            "target": {
                "type": "labor_payment",
                "worker": params.get("worker"),
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
                "worker": params.get("worker"),
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
    if skill_name == "create_operation_work_order":
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
            lines.append(
                f"付款：应付{labor['payable_amount']}元，"
                f"已付{labor['paid_amount']}元，"
                f"未付{labor['unpaid_amount']}元"
            )
        if original_input:
            lines.append(f"理解：您说的是「{original_input}」")
        lines.append("确认吗？")
        return "\n".join(lines)

    if skill_name == "update_crop_cycle":
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


def _build_create_work_order_context(
    skill_name: str,
    params: dict,
    original_input: str,
) -> dict:
    workers = _split_names(params.get("workers"))
    unit_price = _to_decimal(params.get("unit_price")) or Decimal("0")
    paid_amount = _to_decimal(params.get("paid_amount")) or Decimal("0")
    payable = _to_decimal(params.get("payable_amount"))
    total_payable = (payable if payable is not None else unit_price) * len(workers)
    total_paid = paid_amount
    total_unpaid = max(total_payable - total_paid, Decimal("0"))
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
    "store_pending",
    "get_pending",
    "remove_pending",
    "is_write_skill",
    "detect_user_intent",
    "build_confirm_message",
    "build_confirmation_context",
    "is_pending_tool_message",
    "PENDING_MARKER",
    "_pending",
    "WRITE_SKILLS",
    "get_cache_groups_for_skill",
]
