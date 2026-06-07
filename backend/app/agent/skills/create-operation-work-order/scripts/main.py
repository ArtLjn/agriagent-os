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
                "cycle_id": {
                    "type": "integer",
                    "description": "种植批次 ID，不传则自动选择第一个活跃批次",
                },
                "unit_names": {
                    "type": "string",
                    "description": "作用棚/地块名称，多个用逗号分隔，如东大棚 1-3 号,东大棚 4-6 号",
                },
                "note": {
                    "type": "string",
                    "description": "备注",
                },
                "workers": {
                    "type": "string",
                    "description": "工人姓名，多个用逗号分隔；不存在时自动创建轻量档案",
                },
                "unit_price": {
                    "type": "number",
                    "description": "每名工人单价，如 200",
                },
                "paid_worker": {
                    "type": "string",
                    "description": "已付款工人姓名，如老王",
                },
                "paid_amount": {
                    "type": "number",
                    "description": "已付金额，如 200",
                },
            },
            "required": ["operation_type"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
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
            cycle_id = params.get("cycle_id") or _find_first_active_cycle(db, farm_id)
            if not cycle_id:
                return SkillResult(
                    status=ResultStatus.NEED_CLARIFY,
                    reply="当前没有活跃种植批次，请先创建批次。",
                )
            unit_ids = _resolve_unit_ids(
                db, farm_id, cycle_id, params.get("unit_names")
            )
            worker_names = _split_names(params.get("workers"))
            labor_entries = _build_labor_entries(db, farm_id, worker_names, params)
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


def _build_labor_entries(db, farm_id: int, worker_names: list[str], params: dict):
    if not worker_names:
        return []
    unit_price = _to_decimal(params.get("unit_price")) or Decimal("0")
    paid_worker = str(params.get("paid_worker") or "").strip()
    paid_amount = _to_decimal(params.get("paid_amount")) or Decimal("0")
    entries = []
    for name in worker_names:
        worker = _find_or_create_worker(db, farm_id, name, unit_price)
        entry_paid = (
            paid_amount if paid_worker and paid_worker == name else Decimal("0")
        )
        entries.append(
            LaborEntryCreate(
                worker_id=worker.id,
                pay_type="daily",
                quantity=Decimal("1"),
                unit_price=unit_price,
                paid_amount=entry_paid,
            )
        )
    return entries


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


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
