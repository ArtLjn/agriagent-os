"""更新农事作业单 Skill。"""

from datetime import date
from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.models.planting import PlantingUnit
from app.schemas.planting import LaborEntryCreate, OperationWorkOrderUpdate
from app.services import labor_service, planting_read_service, planting_service


class UpdateOperationWorkOrderSkill(Skill):
    """纠正农事作业单。"""

    def name(self) -> str:
        return "update_operation_work_order"

    def description(self) -> str:
        return (
            "修改或纠正已有农事作业单的日期、作业类型、范围、备注、工人、"
            "应付金额和已付金额。需要确认后执行。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "work_order_id": {"type": "integer", "description": "作业单 ID"},
                "operation_date": {
                    "type": "string",
                    "description": "新日期 YYYY-MM-DD",
                },
                "operation_type": {"type": "string", "description": "新作业类型"},
                "scope_type": {
                    "type": "string",
                    "description": "范围类型 cycle/unit/farm",
                },
                "unit_names": {
                    "type": "string",
                    "description": "棚/地块名称，逗号分隔",
                },
                "note": {"type": "string", "description": "备注"},
                "workers": {"type": "string", "description": "工人姓名，逗号分隔"},
                "unit_price": {"type": "number", "description": "每人单价"},
                "payable_amount": {"type": "number", "description": "每人应付金额"},
                "paid_amount": {"type": "number", "description": "每人已付金额"},
            },
            "required": ["work_order_id"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": [
                "operation_work_orders",
                "planting_units",
                "workers",
            ],
            "cache_invalidation": [
                "farm_logs",
                "cost_analytics",
                "cost_summary",
                "get_farm_status",
            ],
            "confirmation_schema": {
                "target_fields": ["work_order_id", "operation_type", "operation_date"],
                "changed_fields": [
                    "operation_date",
                    "operation_type",
                    "scope_type",
                    "unit_names",
                    "note",
                    "workers",
                    "payable_amount",
                    "paid_amount",
                ],
                "inferred_fields": ["work_order_id"],
                "editable_fields": [
                    "operation_date",
                    "operation_type",
                    "scope_type",
                    "unit_names",
                    "note",
                    "workers",
                    "unit_price",
                    "payable_amount",
                    "paid_amount",
                ],
                "risk_notes": ["确认后会修改作业单和关联人工成本。"],
            },
            "evaluation_tags": ["write", "operation_work_order", "labor"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
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
                operation_date=_parse_date(params.get("operation_date")),
                operation_type=_clean(params.get("operation_type")),
                scope_type=_clean(params.get("scope_type")),
                unit_ids=_resolve_unit_ids(
                    db, farm_id, current.cycle_id, params.get("unit_names")
                ),
                note=params.get("note") if "note" in params else None,
                labor_entries=_build_labor_entries(db, farm_id, params),
            )
            updated = planting_service.update_work_order(
                db, int(work_order_id), update, farm_id
            )
            response = planting_read_service.to_work_order_response(updated)
            return SkillResult(
                status=ResultStatus.SUCCESS, reply=_format_reply(response)
            )
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"更新农事作业单失败：{exc}"
            )
        finally:
            db.close()


def _parse_date(value) -> date | None:
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


def _split_names(value) -> list[str]:
    if not value:
        return []
    return [
        part.strip()
        for part in str(value).replace("，", ",").split(",")
        if part.strip()
    ]


def _resolve_unit_ids(
    db, farm_id: int, cycle_id: int | None, value
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
    db, farm_id: int, params: dict
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
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _format_reply(work_order) -> str:
    lines = [
        f"已更新农事作业单 #{work_order.id}：{work_order.operation_type}",
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
