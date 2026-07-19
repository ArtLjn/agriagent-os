"""Pending 工具调用的参数准备辅助逻辑。"""

import logging
import re

from app.agent.runtime.tool_metadata import (
    _LABOR_PAYMENT_SKILL,
    _LABOR_SETTLE_OPERATION,
    _operation_name_from_args,
)
from app.shared.database import SessionLocal
from app.domains.planting.cycle_models import CropCycle
from app.domains.planting.models import Worker
from app.skills.metadata import (
    infer_skill_operation_name,
    resolve_skill_capability_metadata,
)

logger = logging.getLogger(__name__)

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
    _fill_inferred_write_operation(name, execution_args)
    if _operation_name_from_args(name, execution_args) == "create_work_order":
        _normalize_operation_work_order_args(execution_args)
        _fill_operation_default_wage(execution_args, farm_id)
    if _should_force_labor_payment_settle(name, execution_args, original_input):
        execution_args["operation"] = _LABOR_SETTLE_OPERATION
        _normalize_settle_labor_payment_args(execution_args, original_input)
    if name == "manage_workers":
        _fill_manage_workers_target_args(execution_args, farm_id, original_input)
    return execution_args


def _fill_inferred_write_operation(name: str, args: dict) -> None:
    if args.get("operation"):
        return
    operation = infer_skill_operation_name(name, args)
    if not operation:
        return
    metadata = resolve_skill_capability_metadata(name, operation) or {}
    if metadata.get("operation_risk") in {"write_confirm", "write_high"}:
        args["operation"] = operation


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
        args.pop("operation", None)
        args["scope"] = "all_unpaid_labor"


def _is_labor_payment_settle_call(name: str, args: dict) -> bool:
    operation = str(args.get("operation") or "")
    if name == "settle_labor_payment":
        return True
    if name != _LABOR_PAYMENT_SKILL:
        return False
    return operation == _LABOR_SETTLE_OPERATION or any(
        args.get(key) not in (None, "") for key in ("amount", "scope", "payment_date")
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
            if tool_call.get("name")
            not in {"settle_labor_payment", _LABOR_PAYMENT_SKILL}
        ],
    ]


def _ambiguous_debt_direction_message(name: str, args: dict) -> str:
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
        if _pending_cycle_matches(cycle, crop_name=crop_name, cycle_name=cycle_name)
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
        from app.domains.planting import read_service as planting_read_service

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


__all__ = [
    "SessionLocal",
    "_ambiguous_debt_direction_message",
    "_build_pending_confirmation_args",
    "_build_pending_execution_args",
    "_collapse_all_labor_payment_tool_calls",
    "_needs_debt_direction_clarification",
]
