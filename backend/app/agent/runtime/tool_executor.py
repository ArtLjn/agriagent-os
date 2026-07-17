"""Agent Runtime 工具执行。"""

import asyncio
import logging
import re
import time as _time
from dataclasses import dataclass

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.reflector import ReflectorService
from app.agent.reflector.models import ReflectionDecision, ReflectionTrigger
from app.agent.router import SkillRouter
from app.skills import get_langchain_tools
from app.skills.metadata import (
    SkillPermissionLevel,
    resolve_skill_capability_metadata,
)
from app.agent.state import AgentState
from app.core.database import SessionLocal
from app.infra.pending_actions import (
    PENDING_MARKER,
    PendingPlanStep,
    build_confirm_message,
    build_confirmation_context,
    build_plan_confirm_message,
    is_write_skill_call,
    store_pending,
    store_pending_plan,
)
from app.infra.trace_collector import get_collector
from app.infra.trace_context import set_round_index
from app.models.cycle import CropCycle
from app.models.planting import Worker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _PermissionDecision:
    permission_level: str
    requires_confirmation: bool = False
    reject_message: str | None = None
    disabled: bool = False
    disabled_reason: str | None = None
    legacy_alias: str | None = None
    capability: str | None = None
    operation: str | None = None
    operation_risk: str | None = None
    registry_enabled: bool | None = None
    registry_disabled_reason: str | None = None

    @property
    def is_disabled(self) -> bool:
        return self.disabled


_KNOWN_PERMISSION_LEVELS = {level.value for level in SkillPermissionLevel}
_DEBT_DIRECTION_HINT_RE = re.compile(
    r"(?:买|采购|购|花|支出|卖|销售|收入|赚|向|跟|找|在|给|我欠|欠我|未付|未收|先欠着)"
)
_AMBIGUOUS_DEBT_RE = re.compile(
    r"^(?P<name>[\u4e00-\u9fffA-Za-z0-9·]{1,20})(?:赊账|赊了|赊|欠账|欠款|欠)\s*\d*"
)
_ALL_LABOR_PAYMENT_RE = re.compile(
    r"(?:所有|全部|全体|全部的|所有的).{0,8}(?:员工|工人|人工|工资)"
    r"|(?:员工|工人|人工|工资).{0,8}(?:全部|全都|全额|全结|全清)"
)
_SINGLE_LABOR_PAYMENT_RE = re.compile(
    r"(?:补付|支付|结算|付清|结清|结了|结工资)"
    r"|(?:工资|工钱|人工).{0,6}(?:结了|结清|付清)"
)
_LABOR_PAYMENT_QUERY_RE = re.compile(
    r"(?:还欠|欠多少|多少|查询|查一下|看看|未付|应付|人工欠款)"
)
_SETTLE_LABOR_PAYMENT_ALLOWED_ARGS = {
    "operation",
    "scope",
    "worker",
    "worker_id",
    "worker_name",
    "amount",
    "payment_date",
    "cycle_id",
    "work_order_id",
    "start_date",
    "end_date",
}
_LABOR_PAYMENT_SKILL = "manage_labor_payment"
_LABOR_SETTLE_OPERATION = "settle_payment"
_LABOR_QUERY_OPERATION = "query_payables"
_LABOR_WAGE_OPERATION = "manage_wage"
_LABOR_PAYMENT_SETTLE_FIELDS = ("amount", "scope", "payment_date")
_LABOR_PAYMENT_WAGE_FIELDS = (
    "action",
    "labor_entry_id",
    "operation_type",
    "worker_id",
    "pay_type",
    "quantity",
    "unit_price",
    "paid_amount",
    "note",
    "work_date",
    "client_request_id",
)


def _permission_decision(
    tool,
    skill_name: str,
    state: AgentState,
    args: dict | None = None,
) -> _PermissionDecision:
    """根据 metadata 权限等级做执行决策，未知权限按 fail closed 处理。"""
    metadata = getattr(tool, "skill_metadata", None)
    capability_metadata = _capability_metadata_from_runtime(metadata, skill_name, args)
    permission_value = (
        _metadata_permission_value(metadata) if metadata is not None else None
    )
    if capability_metadata.get("registry_enabled") is False:
        return _registry_disabled_permission_decision(
            permission_value,
            skill_name,
            capability_metadata,
        )
    if metadata is None:
        return _legacy_permission_decision(skill_name, capability_metadata)

    if getattr(metadata, "enabled", None) is False:
        return _disabled_permission_decision(
            permission_value,
            skill_name,
            getattr(metadata, "disabled_reason", None),
            capability_metadata,
        )
    if _must_honor_metadata_permission_before_operation(
        permission_value,
        skill_name,
        capability_metadata,
    ):
        return _metadata_permission_decision(
            permission_value,
            skill_name,
            state,
            capability_metadata,
        )
    operation_decision = _operation_risk_decision(capability_metadata)
    if operation_decision is not None:
        return operation_decision
    return _metadata_permission_decision(
        permission_value,
        skill_name,
        state,
        capability_metadata,
    )


def _metadata_permission_value(metadata):
    permission_level = getattr(metadata, "permission_level", None)
    return getattr(permission_level, "value", permission_level)


def _must_honor_metadata_permission_before_operation(
    permission_value,
    skill_name: str,
    capability_metadata: dict,
) -> bool:
    if permission_value == SkillPermissionLevel.ADMIN.value:
        return True
    if permission_value == SkillPermissionLevel.WRITE_CONFIRM.value:
        return capability_metadata.get("operation_risk") != SkillPermissionLevel.READ.value
    if permission_value in {SkillPermissionLevel.EXTERNAL_NETWORK.value}:
        return True
    return isinstance(permission_value, str) and (
        permission_value not in _KNOWN_PERMISSION_LEVELS
        and not is_write_skill_call(skill_name, None)
    )


def _registry_disabled_permission_decision(
    permission_value,
    skill_name: str,
    capability_metadata: dict,
) -> _PermissionDecision:
    return _disabled_permission_decision(
        permission_value,
        skill_name,
        capability_metadata.get("registry_disabled_reason") or "Registry disabled",
        capability_metadata,
    )


def _disabled_permission_decision(
    permission_value,
    skill_name: str,
    disabled_reason: str | None,
    capability_metadata: dict,
) -> _PermissionDecision:
    return _PermissionDecision(
        permission_level=_permission_value_for_disabled(
            permission_value,
            skill_name,
            capability_metadata.get("operation_risk"),
        ),
        disabled=True,
        disabled_reason=disabled_reason,
        **capability_metadata,
    )


def _metadata_permission_decision(
    permission_value,
    skill_name: str,
    state: AgentState,
    capability_metadata: dict,
) -> _PermissionDecision:
    if permission_value in _KNOWN_PERMISSION_LEVELS:
        return _known_permission_decision(permission_value, state, capability_metadata)
    if isinstance(permission_value, str):
        if is_write_skill_call(skill_name, None):
            return _write_confirm_decision(capability_metadata)
        return _PermissionDecision(
            permission_level=permission_value,
            reject_message="工具调用失败：未知权限等级。",
            **capability_metadata,
        )
    return _legacy_permission_decision(skill_name, capability_metadata)


def _known_permission_decision(
    permission_value: str,
    state: AgentState,
    capability_metadata: dict,
) -> _PermissionDecision:
    if permission_value == SkillPermissionLevel.WRITE_CONFIRM.value:
        return _write_confirm_decision(capability_metadata)
    if permission_value == SkillPermissionLevel.ADMIN.value:
        if state.get("user_role") == "admin":
            return _PermissionDecision(
                permission_level=permission_value,
                **capability_metadata,
            )
        return _PermissionDecision(
            permission_level=permission_value,
            reject_message="工具调用失败：需要管理员权限。",
            **capability_metadata,
        )
    return _PermissionDecision(permission_level=permission_value, **capability_metadata)


def _legacy_permission_decision(
    skill_name: str,
    capability_metadata: dict,
) -> _PermissionDecision:
    if is_write_skill_call(skill_name, None):
        return _write_confirm_decision(capability_metadata)

    return _PermissionDecision(
        permission_level=SkillPermissionLevel.READ.value,
        **capability_metadata,
    )


def _write_confirm_decision(capability_metadata: dict) -> _PermissionDecision:
    return _PermissionDecision(
        permission_level=SkillPermissionLevel.WRITE_CONFIRM.value,
        requires_confirmation=True,
        **capability_metadata,
    )


def _capability_metadata_from_runtime(
    metadata,
    skill_name: str,
    args: dict | None = None,
) -> dict:
    """读取 Tool metadata；缺失时用 Registry alias 做兼容解析。"""
    operation_name = _operation_name_from_args(skill_name, args)
    resolved = resolve_skill_capability_metadata(skill_name, operation_name) or {}
    operation = resolved.get("operation") or getattr(metadata, "operation", None)
    operation_risk = resolved.get("operation_risk") or getattr(
        metadata,
        "operation_risk",
        None,
    )
    return {
        "legacy_alias": getattr(metadata, "legacy_alias", None)
        or resolved.get("legacy_alias"),
        "capability": getattr(metadata, "capability", None)
        or resolved.get("capability"),
        "operation": operation,
        "operation_risk": operation_risk,
        "registry_enabled": resolved.get("enabled"),
        "registry_disabled_reason": resolved.get("disabled_reason"),
    }


def _operation_name_from_args(skill_name: str, args: dict | None) -> str | None:
    if not isinstance(args, dict):
        args = {}
    operation = args.get("operation")
    if operation:
        return str(operation)
    resolved = resolve_skill_capability_metadata(skill_name)
    if resolved is not None and resolved.get("operation"):
        return str(resolved["operation"])
    if skill_name == _LABOR_PAYMENT_SKILL:
        return _labor_payment_operation_from_args(args)
    if skill_name == "manage_user_settings":
        write_fields = (
            "display_name",
            "default_city",
            "default_lat",
            "default_lon",
            "assistant_role",
        )
        return (
            "update_settings"
            if any(args.get(key) is not None for key in write_fields)
            else "query_settings"
        )
    return None


def _labor_payment_operation_from_args(args: dict) -> str | None:
    has_settle_fields = any(
        args.get(key) not in (None, "") for key in _LABOR_PAYMENT_SETTLE_FIELDS
    )
    has_wage_fields = any(
        args.get(key) not in (None, "") for key in _LABOR_PAYMENT_WAGE_FIELDS
    )
    if has_settle_fields and _only_labor_payment_worker_id_wage_field(args):
        return _LABOR_SETTLE_OPERATION
    if has_settle_fields and has_wage_fields:
        return None
    if has_settle_fields:
        return _LABOR_SETTLE_OPERATION
    if has_wage_fields:
        return _LABOR_WAGE_OPERATION
    return _LABOR_QUERY_OPERATION


def _only_labor_payment_worker_id_wage_field(args: dict) -> bool:
    wage_keys = {
        key
        for key in _LABOR_PAYMENT_WAGE_FIELDS
        if args.get(key) not in (None, "")
    }
    return wage_keys == {"worker_id"}


def _permission_value_for_disabled(
    permission_value,
    skill_name: str,
    operation_risk: str | None,
) -> str:
    if permission_value in _KNOWN_PERMISSION_LEVELS:
        return permission_value
    if operation_risk == SkillPermissionLevel.EXTERNAL_NETWORK.value:
        return SkillPermissionLevel.EXTERNAL_NETWORK.value
    if operation_risk in {"write_confirm", "write_high"}:
        return SkillPermissionLevel.WRITE_CONFIRM.value
    if operation_risk == SkillPermissionLevel.READ.value:
        return SkillPermissionLevel.READ.value
    if is_write_skill_call(skill_name, None):
        return SkillPermissionLevel.WRITE_CONFIRM.value
    if isinstance(permission_value, str):
        return permission_value
    return SkillPermissionLevel.READ.value


def _operation_risk_decision(
    capability_metadata: dict,
) -> _PermissionDecision | None:
    operation_risk = capability_metadata.get("operation_risk")
    if operation_risk == SkillPermissionLevel.EXTERNAL_NETWORK.value:
        return _PermissionDecision(
            permission_level=SkillPermissionLevel.EXTERNAL_NETWORK.value,
            **capability_metadata,
        )
    if operation_risk in {"write_confirm", "write_high"}:
        return _PermissionDecision(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM.value,
            requires_confirmation=True,
            **capability_metadata,
        )
    if operation_risk == SkillPermissionLevel.READ.value:
        return _PermissionDecision(
            permission_level=SkillPermissionLevel.READ.value,
            **capability_metadata,
        )
    return None


def _permission_trace_output(permission_decision: _PermissionDecision) -> dict:
    payload = {"permission_level": permission_decision.permission_level}
    if permission_decision.legacy_alias:
        payload["legacy_tool_name"] = permission_decision.legacy_alias
    if permission_decision.capability:
        payload["resolved_capability"] = permission_decision.capability
    if permission_decision.operation:
        payload["resolved_operation"] = permission_decision.operation
    if permission_decision.operation_risk:
        payload["operation_risk"] = permission_decision.operation_risk
    return payload


def _build_pending_confirmation_args(name: str, args: dict, farm_id: int) -> dict:
    """构建确认展示用参数，避免修改实际待执行参数。"""
    context_args = dict(args or {})
    if _operation_name_from_args(name, context_args) == "create_work_order":
        _normalize_operation_work_order_args(context_args)
    if name == "update_crop_cycle" or (
        name == "manage_crop_cycle"
        and context_args.get("operation") in {"update_cycle", "update_stage"}
    ):
        _fill_update_crop_cycle_context_args(context_args, farm_id)
    if _is_labor_payment_settle_call(name, context_args):
        _fill_settle_labor_context_args(context_args, farm_id)
    return context_args


def _build_pending_execution_args(
    name: str,
    args: dict,
    farm_id: int,
    original_input: str,
) -> dict:
    """构建待执行参数，只补齐确定性的目标标识。"""
    execution_args = dict(args or {})
    if _operation_name_from_args(name, execution_args) == "create_work_order":
        _normalize_operation_work_order_args(execution_args)
        _fill_operation_default_wage(execution_args, farm_id)
    if _should_force_labor_payment_settle(name, execution_args, original_input):
        execution_args["operation"] = _LABOR_SETTLE_OPERATION
        _normalize_settle_labor_payment_args(execution_args, original_input)
    if name == "manage_workers":
        _fill_manage_workers_target_args(execution_args, farm_id, original_input)
    return execution_args


def _normalize_operation_work_order_args(args: dict) -> None:
    """规范化模型常见作业单参数别名。"""
    _copy_arg_if_missing(args, "operation_date", "work_date")
    _copy_arg_if_missing(args, "unit_names", "planting_unit_name")
    _copy_arg_if_missing(args, "workers", "worker_name")
    _copy_arg_if_missing(args, "pay_type", "payment_method")


def _fill_operation_default_wage(args: dict, farm_id: int) -> None:
    """为单工人作业单补齐可唯一确定的默认工资。"""
    if args.get("unit_price") not in (None, ""):
        return
    worker_names = _split_names_arg(args.get("workers"))
    if len(worker_names) != 1:
        return
    db = SessionLocal()
    try:
        worker = (
            db.query(Worker)
            .filter(Worker.farm_id == farm_id, Worker.name == worker_names[0])
            .order_by(Worker.id)
            .first()
        )
        if worker is None:
            return
        default_unit_price = getattr(worker, "default_unit_price", None)
        if default_unit_price in (None, ""):
            return
        args["unit_price"] = _number_arg(default_unit_price)
        args["unit_price_source"] = "worker_default"
        default_pay_type = getattr(worker, "default_pay_type", None)
        if args.get("pay_type") in (None, "") and default_pay_type:
            args["pay_type"] = str(default_pay_type)
    except Exception as exc:
        logger.warning(
            "补齐作业单默认工资失败 | farm_id=%s | error=%s",
            farm_id,
            exc,
        )
    finally:
        db.close()


def _copy_arg_if_missing(args: dict, target: str, source: str) -> None:
    if args.get(target) in (None, "") and args.get(source) not in (None, ""):
        args[target] = args[source]


def _split_names_arg(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [
        part.strip()
        for part in str(value).replace("，", ",").split(",")
        if part.strip()
    ]


def _number_arg(value):
    try:
        if hasattr(value, "to_integral") and value == value.to_integral():
            return int(value)
    except Exception:
        pass
    return value


def _normalize_settle_labor_payment_args(args: dict, original_input: str) -> None:
    """规范化人工结算参数，避免上下文实体污染全员结算意图。"""
    for key in list(args):
        if key not in _SETTLE_LABOR_PAYMENT_ALLOWED_ARGS:
            args.pop(key, None)
    if _is_all_labor_payment_request(original_input):
        args.pop("worker", None)
        args.pop("worker_name", None)
        args["operation"] = _LABOR_SETTLE_OPERATION
        args["scope"] = "all_unpaid_labor"


def _is_labor_payment_settle_call(name: str, args: dict) -> bool:
    operation = str(args.get("operation") or "")
    if name == "settle_labor_payment":
        return True
    if name != _LABOR_PAYMENT_SKILL:
        return False
    return operation == _LABOR_SETTLE_OPERATION or any(
        args.get(key) not in (None, "")
        for key in ("amount", "scope", "payment_date")
    )


def _should_force_labor_payment_settle(
    name: str, args: dict, original_input: str
) -> bool:
    if _is_labor_payment_settle_call(name, args):
        return True
    if name != _LABOR_PAYMENT_SKILL:
        return False
    if _is_all_labor_payment_request(original_input):
        return True
    return _is_single_labor_payment_request(original_input)


def _is_single_labor_payment_request(original_input: str) -> bool:
    normalized = _normalize_text(original_input)
    if _LABOR_PAYMENT_QUERY_RE.search(normalized):
        return False
    has_labor_target = any(hint in normalized for hint in ("工资", "工钱", "人工"))
    return has_labor_target and bool(_SINGLE_LABOR_PAYMENT_RE.search(normalized))


def _is_all_labor_payment_request(original_input: str) -> bool:
    return bool(_ALL_LABOR_PAYMENT_RE.search(_normalize_text(original_input)))


def _collapse_all_labor_payment_tool_calls(
    tool_calls: list[dict], original_input: str
) -> list[dict]:
    """将全员人工结算拆出的多次单人调用收敛成一次确认。"""
    if not _is_all_labor_payment_request(original_input):
        return tool_calls
    settle_calls = [
        tool_call
        for tool_call in tool_calls
        if tool_call.get("name") in {"settle_labor_payment", _LABOR_PAYMENT_SKILL}
    ]
    if len(settle_calls) <= 1:
        return tool_calls

    collapsed = dict(settle_calls[0])
    collapsed["name"] = _LABOR_PAYMENT_SKILL
    collapsed["args"] = {
        "operation": _LABOR_SETTLE_OPERATION,
        "scope": "all_unpaid_labor",
    }
    return [
        collapsed,
        *[
            tool_call
            for tool_call in tool_calls
            if tool_call.get("name") not in {"settle_labor_payment", _LABOR_PAYMENT_SKILL}
        ],
    ]


def _ambiguous_debt_direction_message(
    name: str,
    args: dict,
) -> str:
    amount = args.get("amount")
    amount_text = f"{amount}元" if amount not in (None, "") else "这笔钱"
    return (
        f"这笔赊账还没有执行。请先确认谁欠谁："
        f"是你欠{name}{amount_text}，还是{name}欠你{amount_text}？"
    )


def _needs_debt_direction_clarification(
    name: str,
    args: dict,
    original_input: str,
) -> str | None:
    is_create_cost_alias = name == "create_cost_record"
    is_manage_cost_create = (
        name == "manage_cost" and args.get("operation") == "create_record"
    )
    if not (is_create_cost_alias or is_manage_cost_create):
        return None
    if args.get("record_subtype") != "赊账":
        return None
    text = original_input.strip()
    if not text or _DEBT_DIRECTION_HINT_RE.search(text):
        return None
    counterparty = str(args.get("counterparty") or "").strip()
    match = _AMBIGUOUS_DEBT_RE.search(text)
    if match:
        return counterparty or match.group("name")
    return None


def _fill_update_crop_cycle_context_args(args: dict, farm_id: int) -> None:
    """为 update_crop_cycle 补齐确认展示所需的当前茬口信息。"""
    needs_lookup = any(
        args.get(key) in (None, "")
        for key in ("old_start_date", "cycle_name", "cycle_id")
    )
    if not needs_lookup:
        return

    db = SessionLocal()
    try:
        cycle = _resolve_pending_crop_cycle(db, args=args, farm_id=farm_id)
        if cycle is None:
            return
        args["cycle_id"] = cycle.id
        args["cycle_name"] = cycle.name
        args["old_start_date"] = _date_to_iso(getattr(cycle, "start_date", None))
    except Exception as exc:
        logger.warning(
            "构建 update_crop_cycle pending context 失败 | farm_id=%s | error=%s",
            farm_id,
            exc,
        )
    finally:
        db.close()


def _resolve_pending_crop_cycle(db, *, args: dict, farm_id: int) -> CropCycle | None:
    cycle_id = args.get("cycle_id")
    if cycle_id not in (None, ""):
        return (
            db.query(CropCycle)
            .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
            .first()
        )

    crop_name = _clean_text(args.get("crop_name"))
    cycle_name = _clean_text(args.get("cycle_name"))
    if not crop_name and not cycle_name:
        return None

    active_cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .all()
    )
    matches = [
        cycle
        for cycle in active_cycles
        if _pending_cycle_matches(
            cycle,
            crop_name=crop_name,
            cycle_name=cycle_name,
        )
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _pending_cycle_matches(
    cycle: CropCycle,
    *,
    crop_name: str | None,
    cycle_name: str | None,
) -> bool:
    cycle_label = _normalize_text(cycle.name)
    template_label = _normalize_text(getattr(cycle.crop_template, "name", ""))

    if cycle_name:
        query = _normalize_text(cycle_name)
        if query in cycle_label or cycle_label in query:
            return True

    if crop_name:
        query = _normalize_text(crop_name)
        return (
            query in cycle_label
            or query in template_label
            or (template_label and template_label in query)
        )

    return False


def _fill_settle_labor_context_args(args: dict, farm_id: int) -> None:
    """为人工结算确认补齐受影响未付条目预览。"""
    if args.get("affected_entries"):
        return
    db = SessionLocal()
    try:
        from app.services import planting_read_service

        worker_name = _clean_text(args.get("worker") or args.get("worker_name"))
        if worker_name is None and args.get("worker_id") not in (None, ""):
            worker = (
                db.query(Worker)
                .filter(Worker.id == int(args["worker_id"]), Worker.farm_id == farm_id)
                .first()
            )
            worker_name = worker.name if worker else None
        entries = planting_read_service.list_labor_payables(
            db,
            farm_id=farm_id,
            worker_name=worker_name,
            cycle_id=args.get("cycle_id"),
            work_order_id=args.get("work_order_id"),
        )
        args["affected_entries"] = [
            {
                "entry_id": entry.id,
                "work_order_id": entry.work_order_id,
                "worker_name": entry.worker.name if entry.worker else "",
                "unpaid_amount": _date_to_iso(entry.unpaid_amount),
            }
            for entry in entries[:10]
        ]
    except Exception as exc:
        logger.warning(
            "构建 manage_labor_payment pending context 失败 | farm_id=%s | error=%s",
            farm_id,
            exc,
        )
    finally:
        db.close()


def _fill_manage_workers_target_args(
    args: dict,
    farm_id: int,
    original_input: str,
) -> None:
    """为工人档案写操作补齐真实 worker_id 和完整姓名。"""
    action = _clean_text(args.get("action")) or "create"
    if action == "create":
        return
    db = SessionLocal()
    try:
        worker = _resolve_pending_worker(db, args=args, farm_id=farm_id)
        if worker is None:
            worker = _resolve_pending_worker_from_input(
                db,
                farm_id=farm_id,
                original_input=original_input,
                name=_clean_text(args.get("name")),
            )
        if worker is None:
            return
        args["worker_id"] = worker.id
        args["name"] = worker.name
    except Exception as exc:
        logger.warning(
            "构建 manage_workers pending args 失败 | farm_id=%s | error=%s",
            farm_id,
            exc,
        )
    finally:
        db.close()


def _resolve_pending_worker(db, *, args: dict, farm_id: int) -> Worker | None:
    worker_id = args.get("worker_id")
    if worker_id not in (None, ""):
        return (
            db.query(Worker)
            .filter(Worker.id == worker_id, Worker.farm_id == farm_id)
            .first()
        )

    name = _clean_text(args.get("name"))
    if not name:
        return None
    return (
        db.query(Worker)
        .filter(Worker.farm_id == farm_id, Worker.name == name)
        .order_by(Worker.id)
        .first()
    )


def _resolve_pending_worker_from_input(
    db,
    *,
    farm_id: int,
    original_input: str,
    name: str | None,
) -> Worker | None:
    if not original_input:
        return None
    workers = (
        db.query(Worker)
        .filter(Worker.farm_id == farm_id)
        .order_by(Worker.id)
        .limit(50)
        .all()
    )
    matches = [
        worker for worker in workers if worker.name and worker.name in original_input
    ]
    if not matches and name:
        matches = [
            worker
            for worker in workers
            if worker.name and (name in worker.name or worker.name in name)
        ]
    if len(matches) == 1:
        return matches[0]
    return None


def _date_to_iso(value) -> str | None:
    try:
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
    except Exception:
        return None


def _clean_text(value) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _normalize_text(value: str) -> str:
    return "".join(str(value).split()).lower()


def _pending_plan_tool_message(
    *,
    state: AgentState,
    farm_id: int,
    original_input: str,
    tool_calls: list[dict],
) -> list[ToolMessage] | None:
    """如果 router 已生成多步骤写计划，则存储 pending plan 并返回确认消息。"""
    plan_draft = state.get("plan_draft")
    draft_steps = _validated_plan_draft_steps(
        plan_draft,
        expected_route_type="write_pending_plan",
    )
    if draft_steps:
        step_tool_names = {str(step["tool_name"]) for step in draft_steps}
        tool_call_names = {str(tool_call["name"]) for tool_call in tool_calls}
        if tool_call_names.issubset(step_tool_names):
            return _store_pending_plan_from_steps(
                state=state,
                farm_id=farm_id,
                original_input=original_input,
                tool_calls=tool_calls,
                steps=draft_steps,
                router_decision=plan_draft,
                source="plan_draft",
            )

    router_decision = state.get("router_decision")
    if router_decision is None:
        return None

    steps = SkillRouter().build_pending_plan_steps(router_decision)
    if len(steps) < 2:
        return None
    step_tool_names = {str(step["tool_name"]) for step in steps}
    tool_call_names = {str(tool_call["name"]) for tool_call in tool_calls}
    if not tool_call_names.issubset(step_tool_names):
        return None

    return _store_pending_plan_from_steps(
        state=state,
        farm_id=farm_id,
        original_input=original_input,
        tool_calls=tool_calls,
        steps=steps,
        router_decision=router_decision.to_trace_payload(),
        source="router_decision",
    )


def _store_pending_plan_from_steps(
    *,
    state: AgentState,
    farm_id: int,
    original_input: str,
    tool_calls: list[dict],
    steps: list[dict],
    router_decision: dict,
    source: str,
) -> list[ToolMessage]:
    """根据已验证步骤创建 pending plan。"""
    step_tool_names = {str(step["tool_name"]) for step in steps}
    pending_steps = [
        PendingPlanStep(
            step_id=str(step["step_id"]),
            step_index=index,
            tool_name=str(step["tool_name"]),
            params=dict(step.get("params") or {}),
            depends_on=list(step.get("depends_on") or []),
        )
        for index, step in enumerate(steps)
    ]
    confirm_text = build_plan_confirm_message(pending_steps)
    reflection_result = ReflectorService().check_pending_plan(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        steps=pending_steps,
        confirmation_text=confirm_text,
        trace_metadata={
            "farm_id": farm_id,
            "session_id": state.get("session_id"),
            "raw_user_input": original_input,
            "tool_names": sorted(step_tool_names),
            "tool_call_ids": [str(tool_call["id"]) for tool_call in tool_calls],
            "plan_draft": state.get("plan_draft") or {},
            "pending_source": source,
        },
    )
    if reflection_result.decision != ReflectionDecision.PASS:
        return [
            ToolMessage(
                content=reflection_result.reason,
                tool_call_id=tool_call["id"],
            )
            for tool_call in tool_calls
        ]

    session_id = state.get("session_id")
    store_pending_plan(
        farm_id=farm_id,
        session_id=session_id,
        raw_user_input=original_input,
        router_decision=router_decision,
        steps=pending_steps,
    )
    messages = [
        ToolMessage(
            content="已纳入待确认计划。",
            tool_call_id=tool_call["id"],
        )
        for tool_call in tool_calls
    ]
    messages[0].content = f"{PENDING_MARKER} {confirm_text}"
    return messages


def _validated_plan_draft_steps(
    plan_draft: dict | None,
    *,
    expected_route_type: str,
) -> list[dict]:
    """读取已经通过验证的 PlanDraft 步骤。"""
    if not isinstance(plan_draft, dict):
        return []
    validation = plan_draft.get("validation")
    if not isinstance(validation, dict) or validation.get("status") != "valid":
        return []
    if plan_draft.get("route_type") != expected_route_type:
        return []
    steps = plan_draft.get("steps")
    if not isinstance(steps, list):
        return []
    normalized: list[dict] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            return []
        tool_name = str(step.get("skill_name") or step.get("tool_name") or "")
        params = step.get("params") or {}
        if not tool_name or not isinstance(params, dict):
            return []
        normalized.append(
            {
                "step_id": str(step.get("step_id") or f"step-{index + 1}"),
                "tool_name": tool_name,
                "params": dict(params),
                "depends_on": list(step.get("depends_on") or []),
            }
        )
    return normalized


def _validated_plan_draft_action_args(
    plan_draft: dict | None,
    *,
    tool_name: str,
) -> dict | None:
    """读取已验证单步写 PlanDraft 的执行参数。"""
    steps = _validated_plan_draft_steps(
        plan_draft,
        expected_route_type="write_pending_action",
    )
    if len(steps) != 1:
        return None
    step = steps[0]
    if step["tool_name"] != tool_name:
        return None
    return dict(step["params"])


def _latest_human_input(state: AgentState) -> str:
    """获取最近一条用户输入，保持原有 200 字截断。"""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content[:200]
    return ""


def _record_pending_plan_trace(collector, original_input: str) -> None:
    collector.record(
        node_type="skill_call",
        node_name="pending_plan",
        input_data={"message": original_input},
        output_data={"status": "pending_plan"},
        duration_ms=0,
    )


def _disabled_tool_message(
    *,
    name: str,
    args: dict,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    """如果工具被禁用，记录 trace 并返回失败消息。"""
    if not permission_decision.is_disabled:
        return None

    output_data = {
        "status": "disabled",
        **_permission_trace_output(permission_decision),
    }
    content = "工具调用失败：工具已禁用。"
    if permission_decision.disabled_reason:
        output_data["disabled_reason"] = permission_decision.disabled_reason
        content = f"{content} 原因：{permission_decision.disabled_reason}"
    logger.warning(
        "Skill 已禁用 | name=%s | permission_level=%s",
        name,
        permission_decision.permission_level,
    )
    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=args,
        output_data=output_data,
        duration_ms=0,
    )
    return ToolMessage(
        content=content,
        tool_call_id=tool_call_id,
    )


def _validation_error_message(
    *,
    tool,
    name: str,
    args: dict,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    """执行 Pydantic 参数校验，失败时反馈 LLM 自纠错。"""
    if not (tool and hasattr(tool, "args_schema") and tool.args_schema):
        return None
    try:
        tool.args_schema.model_validate(args)
    except Exception as e:
        error_msg = f"参数校验失败: {e}"
        logger.warning("Tool 参数校验失败 | name=%s | error=%s", name, e)
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=args,
            output_data={
                "status": "validation_error",
                **_permission_trace_output(permission_decision),
            },
            duration_ms=0,
            error_message=str(e),
        )
        return ToolMessage(
            content=error_msg,
            tool_call_id=tool_call_id,
        )
    return None


def _permission_reject_message(
    *,
    name: str,
    args: dict,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    """处理权限拒绝响应。"""
    if permission_decision.reject_message is None:
        return None

    logger.warning(
        "Skill 权限拒绝 | name=%s | permission_level=%s",
        name,
        permission_decision.permission_level,
    )
    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=args,
        output_data={
            "status": "rejected",
            **_permission_trace_output(permission_decision),
        },
        duration_ms=0,
    )
    return ToolMessage(
        content=permission_decision.reject_message,
        tool_call_id=tool_call_id,
    )


def _resolve_pending_execution_args(
    *,
    state: AgentState,
    name: str,
    args: dict,
    farm_id: int,
    original_input: str,
) -> dict:
    execution_args = _validated_plan_draft_action_args(
        state.get("plan_draft"),
        tool_name=name,
    )
    if execution_args is not None:
        return execution_args
    return _build_pending_execution_args(name, args, farm_id, original_input)


def _ambiguous_pending_message(
    *,
    name: str,
    execution_args: dict,
    original_input: str,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    ambiguous_debt_name = _needs_debt_direction_clarification(
        name, execution_args, original_input
    )
    if not ambiguous_debt_name:
        return None

    content = _ambiguous_debt_direction_message(
        ambiguous_debt_name,
        execution_args,
    )
    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=execution_args,
        output_data={
            "status": "need_clarify",
            "reason": "ambiguous_debt_direction",
            **_permission_trace_output(permission_decision),
        },
        duration_ms=0,
    )
    return ToolMessage(
        content=content,
        tool_call_id=tool_call_id,
    )


def _build_pending_confirmation(
    *,
    name: str,
    execution_args: dict,
    farm_id: int,
    original_input: str,
) -> tuple[dict, str]:
    confirmation_args = _build_pending_confirmation_args(name, execution_args, farm_id)
    confirmation_context = build_confirmation_context(
        name, confirmation_args, original_input=original_input
    )
    confirm_text = build_confirm_message(
        name, confirmation_args, original_input=original_input
    )
    return confirmation_context, confirm_text


def _reflection_block_message(
    *,
    state: AgentState,
    name: str,
    execution_args: dict,
    confirm_text: str,
    farm_id: int,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    reflection_result = ReflectorService().check_write_plan(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        skill_name=name,
        params=execution_args,
        confirmation_text=confirm_text,
        trace_metadata={
            "farm_id": farm_id,
            "session_id": state.get("session_id"),
            "tool_name": name,
            "tool_call_id": tool_call_id,
            "plan_draft": state.get("plan_draft") or {},
        },
    )
    if reflection_result.decision == ReflectionDecision.PASS:
        return None

    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=execution_args,
        output_data={
            "status": "reflection_blocked",
            "reflection": reflection_result.to_trace_payload(),
            **_permission_trace_output(permission_decision),
        },
        duration_ms=0,
    )
    return ToolMessage(
        content=reflection_result.reason,
        tool_call_id=tool_call_id,
    )


def _store_pending_action_message(
    *,
    state: AgentState,
    name: str,
    execution_args: dict,
    original_input: str,
    confirmation_context: dict,
    confirm_text: str,
    farm_id: int,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage:
    session_id = state.get("session_id")
    action_id = store_pending(
        farm_id,
        name,
        execution_args,
        original_input=original_input,
        confirmation_context=confirmation_context,
        session_id=session_id,
    )
    logger.info(
        "写操作 Skill 已拦截 | farm=%s action_id=%s skill=%s",
        farm_id,
        action_id,
        name,
    )
    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=execution_args,
        output_data={
            "status": "pending",
            "confirmation_context": confirmation_context,
            "plan_draft": state.get("plan_draft") or {},
            **_permission_trace_output(permission_decision),
        },
        duration_ms=0,
    )
    return ToolMessage(
        content=f"{PENDING_MARKER} {confirm_text}",
        tool_call_id=tool_call_id,
    )


def _pending_action_message(
    *,
    state: AgentState,
    name: str,
    args: dict,
    farm_id: int,
    original_input: str,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    """写操作 Skill 拦截：存储 pending action，不直接执行。"""
    if not permission_decision.requires_confirmation:
        return None

    execution_args = _resolve_pending_execution_args(
        state=state,
        name=name,
        args=args,
        farm_id=farm_id,
        original_input=original_input,
    )
    ambiguous_message = _ambiguous_pending_message(
        name=name,
        execution_args=execution_args,
        original_input=original_input,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if ambiguous_message is not None:
        return ambiguous_message

    confirmation_context, confirm_text = _build_pending_confirmation(
        name=name,
        execution_args=execution_args,
        farm_id=farm_id,
        original_input=original_input,
    )
    reflection_message = _reflection_block_message(
        state=state,
        name=name,
        execution_args=execution_args,
        confirm_text=confirm_text,
        farm_id=farm_id,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if reflection_message is not None:
        return reflection_message

    return _store_pending_action_message(
        state=state,
        name=name,
        execution_args=execution_args,
        original_input=original_input,
        confirmation_context=confirmation_context,
        confirm_text=confirm_text,
        farm_id=farm_id,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )


def _success_trace_output(result, permission_decision: _PermissionDecision) -> dict:
    """组装工具成功 trace metadata。"""
    trace_output = getattr(result, "trace_data", None)
    if not trace_output:
        trace_output = {
            "status": "success",
            "reply_preview": str(result)[:500],
        }
    else:
        trace_output["reply_preview"] = str(result)[:500]
    trace_output.update(_permission_trace_output(permission_decision))
    return trace_output


async def _invoke_read_tool_message(
    *,
    tool,
    name: str,
    args: dict,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
    start: float,
) -> ToolMessage:
    """执行读操作工具并记录结果 metadata。"""
    if not tool:
        return ToolMessage(content=f"未知工具: {name}", tool_call_id=tool_call_id)
    try:
        result = await tool.ainvoke(args)
        duration_ms = int((_time.perf_counter() - start) * 1000)
        logger.info(
            "Skill 完成 | name=%s | duration_ms=%d | result=%s",
            name,
            duration_ms,
            str(result)[:120].replace("\n", " "),
        )
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=args,
            output_data=_success_trace_output(result, permission_decision),
            duration_ms=duration_ms,
        )
        return ToolMessage(
            content=str(result),
            tool_call_id=tool_call_id,
            name=name,
            additional_kwargs=_tool_message_kwargs(name, args),
        )
    except Exception as e:
        duration_ms = int((_time.perf_counter() - start) * 1000)
        logger.error(
            "Skill 失败 | name=%s | error=%s",
            name,
            e,
        )
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=args,
            duration_ms=duration_ms,
            error_message=str(e),
        )
        return ToolMessage(content=f"工具调用失败: {e}", tool_call_id=tool_call_id)


def _tool_message_kwargs(name: str, args: dict) -> dict:
    if name in {"manage_cost", "manage_farm_logs", "manage_work_orders"} and args.get(
        "operation"
    ):
        return {"operation": str(args["operation"])}
    return {}


def _runtime_tool_for_call(name: str, args: dict, tool_map: dict):
    """按 registry alias 解析实际 runtime tool。"""
    resolved = resolve_skill_capability_metadata(name, args.get("operation")) or {}
    canonical_name = resolved.get("capability") or name
    return tool_map.get(name) or tool_map.get(canonical_name)


def _execution_args_for_call(name: str, args: dict) -> dict:
    """为 legacy alias 调用补齐 registry operation。"""
    execution_args = dict(args or {})
    resolved = resolve_skill_capability_metadata(
        name,
        execution_args.get("operation"),
    )
    if resolved is not None and resolved.get("operation"):
        execution_args.setdefault("operation", resolved["operation"])
    return execution_args


async def _call_one(
    *,
    tc: dict,
    tool_map: dict,
    state: AgentState,
    farm_id: int,
    original_input: str,
    collector,
) -> ToolMessage:
    """执行单个 tool_call，保持原有权限、pending 和 trace 顺序。"""
    name = tc["name"]
    raw_args = _execution_args_for_call(name, tc["args"])
    # 权限判定必须使用已补齐的确定性 operation，否则“结工资”这类写意图会被误判为查询。
    args = _build_pending_execution_args(name, raw_args, farm_id, original_input)
    tool_call_id = tc["id"]
    logger.info("Skill 调用 %s(%s)", name, args)
    start = _time.perf_counter()

    tool = _runtime_tool_for_call(name, args, tool_map)
    permission_decision = _permission_decision(tool, name, state, args)

    message = _disabled_tool_message(
        name=name,
        args=args,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if message is not None:
        return message

    message = _validation_error_message(
        tool=tool,
        name=name,
        args=args,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if message is not None:
        return message

    message = _permission_reject_message(
        name=name,
        args=args,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if message is not None:
        return message

    message = _pending_action_message(
        state=state,
        name=name,
        args=args,
        farm_id=farm_id,
        original_input=original_input,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if message is not None:
        return message

    return await _invoke_read_tool_message(
        tool=tool,
        name=name,
        args=args,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
        start=start,
    )


async def _parallel_tool_node(state: AgentState) -> dict:
    """并行执行多个 tool_calls 的节点。写操作 Skill 拦截为 pending action。"""
    set_round_index(state.get("trace_round_index"))
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    farm_id = state.get("farm_id")
    if not isinstance(farm_id, int) or farm_id <= 0:
        return {
            "messages": [
                ToolMessage(
                    content="工具调用失败：缺少可信农场上下文。",
                    tool_call_id=tc["id"],
                )
                for tc in last.tool_calls
            ]
        }
    farm_uid = state.get("farm_uid")
    tool_map = {
        t.name: t for t in get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
    }
    collector = get_collector()

    original_input = _latest_human_input(state)

    tool_calls = _collapse_all_labor_payment_tool_calls(last.tool_calls, original_input)
    plan_messages = _pending_plan_tool_message(
        state=state,
        farm_id=farm_id,
        original_input=original_input,
        tool_calls=tool_calls,
    )
    if plan_messages is not None:
        _record_pending_plan_trace(collector, original_input)
        return {"messages": plan_messages}

    if len(tool_calls) == 1:
        results = [
            await _call_one(
                tc=tool_calls[0],
                tool_map=tool_map,
                state=state,
                farm_id=farm_id,
                original_input=original_input,
                collector=collector,
            )
        ]
    else:
        logger.info("并行执行 %d 个 Skill", len(tool_calls))
        batch_start = _time.perf_counter()
        results = await asyncio.gather(
            *[
                _call_one(
                    tc=tc,
                    tool_map=tool_map,
                    state=state,
                    farm_id=farm_id,
                    original_input=original_input,
                    collector=collector,
                )
                for tc in tool_calls
            ]
        )
        batch_duration = int((_time.perf_counter() - batch_start) * 1000)
        collector.record(
            node_type="parallel_batch",
            node_name=f"parallel_{len(results)}_skills",
            output_data={
                "parallel_count": len(results),
                "skills": [{"name": tc["name"]} for tc in tool_calls],
            },
            duration_ms=batch_duration,
        )

    return {"messages": results}


__all__ = ["_parallel_tool_node"]
