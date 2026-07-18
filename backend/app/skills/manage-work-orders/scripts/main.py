"""管理农事作业单 Skill。"""

from datetime import date
from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.skills.context import require_farm_context
from app.shared.database import SessionLocal
from app.models.cycle import CropCycle
from app.models.planting import PlantingUnit, Worker
from app.schemas.planting import (
    LaborEntryCreate,
    OperationWorkOrderCreate,
    OperationWorkOrderUpdate,
)
from app.services import labor_service, planting_read_service, planting_service

from .schema import work_order_metadata, work_order_parameters_schema


class ManageWorkOrdersSkill(Skill):
    """创建、查询或更新农事作业单。"""

    def name(self) -> str:
        return "manage_work_orders"

    def description(self) -> str:
        return (
            "管理农事作业单：创建新的采收、授粉等作业单，查询近期作业，"
            "或修改已有作业单的日期、范围、备注和用工信息。"
        )

    def parameters_schema(self) -> dict:
        return work_order_parameters_schema()

    def metadata(self) -> dict:
        return work_order_metadata()

    async def execute(self, params: dict, context) -> SkillResult:
        params = _normalize_params(params)
        operation = str(params.get("operation") or "").strip()
        if operation == "create_work_order":
            return await _create_work_order(params, context)
        if operation == "query_work_orders":
            return await _query_work_orders(params, context)
        if operation == "update_work_order":
            return await _update_work_order(params, context)
        return SkillResult(
            status=ResultStatus.FAILED,
            reply=(
                "管理农事作业单失败：operation 必须是 "
                "create_work_order、query_work_orders 或 update_work_order。"
            ),
        )


async def _create_work_order(params: dict, context) -> SkillResult:
    farm_id, context_error = require_farm_context(context, "创建农事作业单")
    if context_error:
        return context_error
    operation_type = str(params.get("operation_type") or "").strip()
    if not operation_type:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply="创建农事作业单失败：请提供作业类型。",
        )

    db = SessionLocal()
    try:
        create_payload = _build_create_work_order_payload(
            db, farm_id, operation_type, params
        )
        if isinstance(create_payload, SkillResult):
            return create_payload
        work_order = planting_service.create_work_order(
            db,
            create_payload,
            farm_id=farm_id,
        )
        response = planting_read_service.to_work_order_response(work_order)
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=_format_reply(response, prefix="已创建农事作业单"),
        )
    except Exception as exc:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply=f"创建农事作业单失败：{exc}",
        )
    finally:
        db.close()

async def _query_work_orders(params: dict, context) -> SkillResult:
    farm_id, context_error = require_farm_context(context, "查询农事作业单")
    if context_error:
        return context_error
    db = SessionLocal()
    try:
        items = planting_read_service.list_operation_work_orders(
            db,
            farm_id=farm_id,
            cycle_id=params.get("cycle_id"),
            cycle_name=_clean(params.get("cycle_name")),
            unit_id=params.get("unit_id"),
            unit_name=_clean(params.get("unit_name")),
            operation_type=_clean(params.get("operation_type")),
            worker_name=_clean(params.get("worker")),
            start_date=_parse_optional_date(params.get("start_date")),
            end_date=_parse_optional_date(params.get("end_date")),
            payment_status=_clean(params.get("payment_status")),
            limit=int(params.get("limit") or 20),
        )
        if not items:
            return SkillResult(
                status=ResultStatus.SUCCESS, reply="未找到匹配的农事作业单。"
            )
        return SkillResult(status=ResultStatus.SUCCESS, reply=_format_query_reply(items))
    except Exception as exc:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply=f"查询农事作业单失败：{exc}",
        )
    finally:
        db.close()


async def _update_work_order(params: dict, context) -> SkillResult:
    farm_id, context_error = require_farm_context(context, "更新农事作业单")
    if context_error:
        return context_error
    work_order_id = params.get("work_order_id")
    if not work_order_id:
        return SkillResult(
            status=ResultStatus.FAILED,
            reply="更新农事作业单失败：请提供 work_order_id。",
        )
    db = SessionLocal()
    try:
        current = planting_service.get_work_order(db, int(work_order_id), farm_id)
        if not current:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="更新农事作业单失败：未找到作业单。",
            )
        update = OperationWorkOrderUpdate(
            operation_date=_parse_optional_date(params.get("operation_date")),
            operation_type=_clean(params.get("operation_type")),
            scope_type=_clean(params.get("scope_type")),
            unit_ids=_resolve_update_unit_ids(
                db, farm_id, current.cycle_id, params.get("unit_names")
            ),
            note=params.get("note") if "note" in params else None,
            labor_entries=_build_update_labor_entries(db, farm_id, params),
        )
        updated = planting_service.update_work_order(
            db, int(work_order_id), update, farm_id
        )
        response = planting_read_service.to_work_order_response(updated)
        return SkillResult(
            status=ResultStatus.SUCCESS,
            reply=_format_reply(response, prefix=f"已更新农事作业单 #{response.id}"),
        )
    except Exception as exc:
        return SkillResult(
            status=ResultStatus.FAILED, reply=f"更新农事作业单失败：{exc}"
        )
    finally:
        db.close()


def _normalize_params(params: dict) -> dict:
    """规范化模型常见别名参数。"""
    normalized = dict(params or {})
    _copy_if_missing(normalized, "operation_date", "work_date")
    _copy_if_missing(normalized, "unit_names", "planting_unit_name")
    _copy_if_missing(normalized, "workers", "worker_name")
    _copy_if_missing(normalized, "pay_type", "payment_method")
    return normalized


def _copy_if_missing(params: dict, target: str, source: str) -> None:
    if params.get(target) in (None, "") and params.get(source) not in (None, ""):
        params[target] = params[source]


def _build_create_work_order_payload(
    db,
    farm_id: int,
    operation_type: str,
    params: dict,
) -> OperationWorkOrderCreate | SkillResult:
    cycle_id = (
        params.get("cycle_id")
        or _find_cycle_by_name(db, farm_id, params.get("crop_cycle_name"))
        or _find_first_active_cycle(db, farm_id)
    )
    if not cycle_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply="当前没有活跃种植批次，请先创建批次。",
        )
    unit_ids = _resolve_unit_ids(db, farm_id, cycle_id, params.get("unit_names"))
    labor_entries, labor_error = _build_labor_entries(
        db, farm_id, _split_names(params.get("workers")), params
    )
    if labor_error:
        return SkillResult(status=ResultStatus.NEED_CLARIFY, reply=labor_error)
    return OperationWorkOrderCreate(
        cycle_id=cycle_id,
        operation_type=operation_type,
        operation_date=_parse_date(params.get("operation_date")),
        scope_type="unit" if unit_ids else "cycle",
        unit_ids=unit_ids,
        note=params.get("note"),
        labor_entries=labor_entries,
    )


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return date.today()


def _parse_optional_date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _clean(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _find_first_active_cycle(db, farm_id: int) -> int | None:
    cycle = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .order_by(CropCycle.id)
        .first()
    )
    return cycle.id if cycle else None


def _find_cycle_by_name(db, farm_id: int, value) -> int | None:
    name = str(value or "").strip()
    if not name:
        return None
    cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .order_by(CropCycle.id)
        .all()
    )
    matches = [
        cycle
        for cycle in cycles
        if name == getattr(cycle, "name", None)
        or name in str(getattr(cycle, "name", ""))
    ]
    if len(matches) == 1:
        return matches[0].id
    return None


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


def _resolve_unit_ids(db, farm_id: int, cycle_id: int, value) -> list[int]:
    names = _split_names(value)
    if not names:
        return []
    units = (
        db.query(PlantingUnit)
        .filter(
            PlantingUnit.farm_id == farm_id,
            PlantingUnit.cycle_id == cycle_id,
            PlantingUnit.name.in_(names),
        )
        .all()
    )
    return [unit.id for unit in units]


def _resolve_update_unit_ids(
    db,
    farm_id: int,
    cycle_id: int | None,
    value,
) -> list[int] | None:
    names = _split_names(value)
    if not names:
        return None
    query = db.query(PlantingUnit).filter(
        PlantingUnit.farm_id == farm_id,
        PlantingUnit.name.in_(names),
    )
    if cycle_id is not None:
        query = query.filter(PlantingUnit.cycle_id == cycle_id)
    return [unit.id for unit in query.all()]


def _build_labor_entries(
    db, farm_id: int, worker_names: list[str], params: dict
) -> tuple[list[LaborEntryCreate], str | None]:
    if not worker_names:
        return [], None
    explicit_unit_price = _to_decimal(params.get("unit_price"))
    explicit_no_wage = _is_explicit_no_wage(
        params.get("no_wage"), params.get("wage_policy")
    )
    pay_type_param = str(params.get("pay_type") or "").strip()
    paid_worker = str(params.get("paid_worker") or "").strip()
    paid_amount = _to_decimal(params.get("paid_amount")) or Decimal("0")
    quantity = _to_decimal(params.get("quantity")) or Decimal("1")
    entries = []
    for name in worker_names:
        worker = _find_or_create_worker(
            db,
            farm_id,
            name,
            explicit_unit_price or Decimal("0"),
        )
        unit_price = _resolve_labor_unit_price(
            worker=worker,
            explicit_unit_price=explicit_unit_price,
            explicit_no_wage=explicit_no_wage,
        )
        if unit_price is None:
            return [], (
                f"请补充{name}本次作业的工资。"
                "系统不会默认记为0；如果本次不计工资，请明确说明不计工资。"
            )
        pay_type = _resolve_labor_pay_type(worker, pay_type_param)
        entry_paid = (
            paid_amount if paid_worker and paid_worker == name else Decimal("0")
        )
        entries.append(
            LaborEntryCreate(
                worker_id=worker.id,
                pay_type=pay_type,
                quantity=quantity,
                unit_price=unit_price,
                paid_amount=entry_paid,
            )
        )
    return entries, None


def _build_update_labor_entries(
    db,
    farm_id: int,
    params: dict,
) -> list[LaborEntryCreate] | None:
    names = _split_names(params.get("workers"))
    if not names:
        return None
    unit_price = _to_decimal(params.get("unit_price"))
    payable = _to_decimal(params.get("payable_amount"))
    paid = _to_decimal(params.get("paid_amount")) or Decimal("0")
    entries = []
    for name in names:
        worker = labor_service.find_or_create_worker_by_name(
            db, farm_id, name, unit_price or payable
        )
        price = unit_price or payable or worker.default_unit_price or Decimal("0")
        entries.append(
            LaborEntryCreate(
                worker_id=worker.id,
                quantity=Decimal("1"),
                unit_price=price,
                payable_amount=payable,
                paid_amount=paid,
            )
        )
    return entries


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not decimal_value.is_finite():
        return None
    return decimal_value


def _is_explicit_no_wage(no_wage, wage_policy) -> bool:
    if no_wage is True:
        return True
    if isinstance(no_wage, str) and no_wage.strip().lower() in {
        "true",
        "yes",
        "y",
        "1",
    }:
        return True
    return str(wage_policy or "").strip().lower() in {"none", "no_wage", "free"}


def _resolve_labor_unit_price(
    *,
    worker: Worker,
    explicit_unit_price: Decimal | None,
    explicit_no_wage: bool,
) -> Decimal | None:
    if explicit_unit_price is not None:
        return explicit_unit_price
    if explicit_no_wage:
        return Decimal("0")
    default_unit_price = _to_decimal(getattr(worker, "default_unit_price", None))
    if default_unit_price is not None:
        return default_unit_price
    return None


def _resolve_labor_pay_type(worker: Worker, explicit_pay_type: str) -> str:
    if explicit_pay_type:
        return explicit_pay_type
    default_pay_type = getattr(worker, "default_pay_type", None)
    if isinstance(default_pay_type, str) and default_pay_type.strip():
        return default_pay_type.strip()
    return "daily"


def _find_or_create_worker(db, farm_id: int, name: str, unit_price: Decimal) -> Worker:
    worker = (
        db.query(Worker).filter(Worker.farm_id == farm_id, Worker.name == name).first()
    )
    if worker:
        return worker
    worker = Worker(
        farm_id=farm_id,
        name=name,
        default_pay_type="daily",
        default_unit_price=unit_price if unit_price > 0 else None,
    )
    db.add(worker)
    db.flush()
    return worker


def _format_query_reply(items) -> str:
    lines = ["匹配的农事作业单："]
    for item in items:
        response = planting_read_service.to_work_order_response(item)
        scope = "、".join(response.unit_names) or response.cycle_name or response.scope_type
        workers = "、".join(
            entry.worker_name or f"工人{entry.worker_id}"
            for entry in response.labor_entries
        )
        if not workers:
            workers = "无用工"
        lines.append(
            f"- #{response.id} {response.operation_date} {response.operation_type}"
            f"｜范围：{scope}｜工人：{workers}｜"
            f"应付{response.total_payable_amount}元，"
            f"已付{response.total_paid_amount}元，"
            f"未付{response.total_unpaid_amount}元"
        )
    return "\n".join(lines)


def _format_reply(work_order, *, prefix: str) -> str:
    lines = [
        f"{prefix}：{work_order.operation_type}",
        f"日期：{work_order.operation_date}",
    ]
    if work_order.unit_names:
        lines.append(f"范围：{'、'.join(work_order.unit_names)}")
    if work_order.labor_entries:
        lines.append(
            f"人工：应付{work_order.total_payable_amount}元，"
            f"已付{work_order.total_paid_amount}元，"
            f"未付{work_order.total_unpaid_amount}元"
        )
    return "\n".join(lines)
