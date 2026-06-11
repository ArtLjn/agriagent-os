"""创建农事作业单 Skill。"""

from datetime import date
from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.models.cycle import CropCycle
from app.models.planting import PlantingUnit, Worker
from app.schemas.planting import LaborEntryCreate, OperationWorkOrderCreate
from app.services import planting_read_service, planting_service


class CreateOperationWorkOrderSkill(Skill):
    """创建农事作业单，可同时记录用工。"""

    def name(self) -> str:
        return "create_operation_work_order"

    def description(self) -> str:
        return (
            "创建农事作业单，适合记录授粉、压蔓、留瓜、垫瓜、采收、装车等农事。"
            "可同时记录多个工人、计薪方式、数量、单价、已付金额，并自动计入人工成本。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation_type": {
                    "type": "string",
                    "description": "作业类型，如人工授粉、压蔓、装车",
                },
                "operation_date": {
                    "type": "string",
                    "description": "作业日期 YYYY-MM-DD，默认今天",
                },
                "work_date": {
                    "type": "string",
                    "description": "作业日期别名，YYYY-MM-DD",
                },
                "cycle_id": {
                    "type": "integer",
                    "description": "种植批次 ID，不传则自动选择第一个活跃批次",
                },
                "crop_cycle_name": {
                    "type": "string",
                    "description": "茬口名称别名，如水稻、夏季水稻",
                },
                "unit_names": {
                    "type": "string",
                    "description": "作用棚/地块名称，多个用逗号分隔，如东大棚 1-3 号,东大棚 4-6 号",
                },
                "planting_unit_name": {
                    "type": "string",
                    "description": "棚/地块名称别名，如1号棚",
                },
                "note": {
                    "type": "string",
                    "description": "备注",
                },
                "workers": {
                    "type": "string",
                    "description": "工人姓名，多个用逗号分隔；不存在时自动创建轻量档案",
                },
                "worker_name": {
                    "type": "string",
                    "description": "工人姓名别名，如李丽",
                },
                "unit_price": {
                    "type": "number",
                    "description": "每名工人单价，如 200",
                },
                "payment_method": {
                    "type": "string",
                    "description": "计薪方式别名，如 daily、hourly、piece",
                },
                "paid_worker": {
                    "type": "string",
                    "description": "已付款工人姓名，如老王",
                },
                "paid_amount": {
                    "type": "number",
                    "description": "已付金额，如 200",
                },
                "no_wage": {
                    "type": "boolean",
                    "description": "明确表示本次作业不计工资时传 true",
                },
                "wage_policy": {
                    "type": "string",
                    "description": "工资策略；不计工资时可传 none、no_wage 或 free",
                },
            },
            "required": ["operation_type"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        params = _normalize_params(params)
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
            unit_ids = _resolve_unit_ids(
                db, farm_id, cycle_id, params.get("unit_names")
            )
            worker_names = _split_names(params.get("workers"))
            labor_entries, labor_error = _build_labor_entries(
                db, farm_id, worker_names, params
            )
            if labor_error:
                return SkillResult(
                    status=ResultStatus.NEED_CLARIFY,
                    reply=labor_error,
                )
            scope_type = "unit" if unit_ids else "cycle"
            work_order = planting_service.create_work_order(
                db,
                OperationWorkOrderCreate(
                    cycle_id=cycle_id,
                    operation_type=operation_type,
                    operation_date=_parse_date(params.get("operation_date")),
                    scope_type=scope_type,
                    unit_ids=unit_ids,
                    note=params.get("note"),
                    labor_entries=labor_entries,
                ),
                farm_id=farm_id,
            )
            response = planting_read_service.to_work_order_response(work_order)
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=_format_reply(response),
            )
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"创建农事作业单失败：{exc}",
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


def _parse_date(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return date.today()


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


def _build_labor_entries(
    db, farm_id: int, worker_names: list[str], params: dict
) -> tuple[list[LaborEntryCreate], str | None]:
    if not worker_names:
        return [], None
    explicit_unit_price = _to_decimal(params.get("unit_price"))
    explicit_no_wage = bool(params.get("no_wage")) or str(
        params.get("wage_policy") or ""
    ).strip() in {"none", "no_wage", "free"}
    pay_type_param = str(params.get("pay_type") or "").strip()
    paid_worker = str(params.get("paid_worker") or "").strip()
    paid_amount = _to_decimal(params.get("paid_amount")) or Decimal("0")
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
                quantity=Decimal("1"),
                unit_price=unit_price,
                paid_amount=entry_paid,
            )
        )
    return entries, None


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


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


def _format_reply(work_order) -> str:
    lines = [
        f"已创建农事作业单：{work_order.operation_type}",
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
