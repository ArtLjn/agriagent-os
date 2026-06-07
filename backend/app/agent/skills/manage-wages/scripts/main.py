"""工资记录管理 Skill。"""

from datetime import date
from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.schemas.planting import WageSaveRequest, WageUpdateRequest
from app.services import labor_service, planting_read_service


class ManageWagesSkill(Skill):
    """保存或更新独立工资记录。"""

    def name(self) -> str:
        return "manage_wages"

    def description(self) -> str:
        return (
            "保存或更新独立工资记录，并同步人工成本账单。新增工资必须提供茬口、"
            "工人、作业类型、日期、数量和单价；修改工资可按工资记录 ID 调整金额、"
            "已付金额、日期、工人或备注。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作：save/update"},
                "labor_entry_id": {"type": "integer", "description": "工资记录 ID"},
                "cycle_id": {"type": "integer", "description": "茬口 ID"},
                "operation_type": {
                    "type": "string",
                    "description": "作业类型，如采收、装车、整枝打杈",
                },
                "worker_id": {"type": "integer", "description": "工人 ID"},
                "worker_name": {"type": "string", "description": "工人姓名"},
                "pay_type": {
                    "type": "string",
                    "description": "计薪方式，如 daily、hourly、piece",
                },
                "quantity": {"type": "number", "description": "数量，如天数/小时/件数"},
                "unit_price": {"type": "number", "description": "单价"},
                "paid_amount": {"type": "number", "description": "已付金额"},
                "note": {"type": "string", "description": "备注"},
                "work_date": {
                    "type": "string",
                    "description": "作业/工资日期 YYYY-MM-DD；新增工资必填",
                },
                "client_request_id": {
                    "type": "string",
                    "description": "幂等键；不传时由参数生成稳定键",
                },
            },
            "required": ["action"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": ["workers", "crop_cycles", "unpaid_labor"],
            "cache_invalidation": [
                "cost_analytics",
                "cost_summary",
                "get_farm_status",
            ],
            "confirmation_schema": {
                "target_fields": [
                    "action",
                    "labor_entry_id",
                    "worker_name",
                    "worker_id",
                ],
                "changed_fields": [
                    "cycle_id",
                    "operation_type",
                    "pay_type",
                    "quantity",
                    "unit_price",
                    "paid_amount",
                    "work_date",
                    "note",
                ],
                "inferred_fields": ["client_request_id"],
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
                "risk_notes": ["确认后会创建或更新工资记录，并同步人工成本账单。"],
            },
            "evaluation_tags": ["write", "labor", "wage"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "管理工资")
        if context_error:
            return context_error

        action = _clean(params.get("action")) or "save"
        db = SessionLocal()
        try:
            if action == "save":
                data = _build_save_request(params)
                entry, cost_record_id = labor_service.save_wage_entry(db, data, farm_id)
            elif action == "update":
                labor_entry_id = params.get("labor_entry_id")
                if not labor_entry_id:
                    return SkillResult(
                        status=ResultStatus.NEED_CLARIFY,
                        reply="修改工资需要工资记录 ID。",
                    )
                data = _build_update_request(params)
                entry, cost_record_id = labor_service.update_wage_entry(
                    db, int(labor_entry_id), data, farm_id
                )
            else:
                return SkillResult(
                    status=ResultStatus.FAILED,
                    reply="管理工资失败：action 必须是 save 或 update。",
                )
            response = planting_read_service.to_wage_response(entry, cost_record_id)
            return SkillResult(
                status=ResultStatus.SUCCESS, reply=_format_reply(action, response)
            )
        except ValueError as exc:
            return SkillResult(status=ResultStatus.NEED_CLARIFY, reply=str(exc))
        except Exception as exc:
            return SkillResult(status=ResultStatus.FAILED, reply=f"管理工资失败：{exc}")
        finally:
            db.close()


def _build_save_request(params: dict) -> WageSaveRequest:
    worker_id = params.get("worker_id")
    worker_name = _clean(params.get("worker_name"))
    if not worker_id and not worker_name:
        raise ValueError("新增工资需要工人姓名或 worker_id。")
    work_date = _parse_date(params.get("work_date"))
    if work_date is None:
        raise ValueError("新增工资需要明确日期，请提供 work_date。")
    cycle_id = params.get("cycle_id")
    if not cycle_id:
        raise ValueError("新增工资需要关联茬口 cycle_id。")
    operation_type = _clean(params.get("operation_type"))
    if not operation_type:
        raise ValueError("新增工资需要作业类型 operation_type。")
    unit_price = _to_decimal(params.get("unit_price"))
    if unit_price is None:
        raise ValueError("新增工资需要单价 unit_price。")
    quantity = _to_decimal(params.get("quantity")) or Decimal("1")
    paid_amount = _to_decimal(params.get("paid_amount")) or Decimal("0")
    return WageSaveRequest(
        cycle_id=int(cycle_id),
        operation_type=operation_type,
        worker_id=int(worker_id) if worker_id else None,
        worker_name=worker_name,
        pay_type=_clean(params.get("pay_type")) or "daily",
        quantity=quantity,
        unit_price=unit_price,
        paid_amount=paid_amount,
        note=_clean(params.get("note")),
        work_date=work_date,
        client_request_id=_client_request_id(params, work_date, worker_name, worker_id),
    )


def _build_update_request(params: dict) -> WageUpdateRequest:
    values = {}
    if params.get("cycle_id") is not None:
        values["cycle_id"] = int(params["cycle_id"])
    for key in ("operation_type", "worker_name", "pay_type", "note"):
        if key in params and params.get(key) is not None:
            values[key] = _clean(params.get(key))
    if params.get("worker_id") is not None:
        values["worker_id"] = int(params["worker_id"])
    for key in ("quantity", "unit_price", "paid_amount"):
        if key in params and params.get(key) is not None:
            values[key] = _to_decimal(params.get(key))
    if params.get("work_date") is not None:
        parsed = _parse_date(params.get("work_date"))
        if parsed is None:
            raise ValueError("work_date 必须是 YYYY-MM-DD。")
        values["work_date"] = parsed
    return WageUpdateRequest(**values)


def _format_reply(action: str, response) -> str:
    action_text = "已更新工资" if action == "update" else "已保存工资"
    return (
        f"{action_text}：{response.worker_name} {response.operation_type}，"
        f"应付{response.payable_amount}元，已付{response.paid_amount}元，"
        f"未付{response.unpaid_amount}元。"
    )


def _client_request_id(
    params: dict, work_date: date, worker_name: str | None, worker_id: int | None
) -> str:
    existing = _clean(params.get("client_request_id"))
    if existing:
        return existing
    worker_key = worker_name or f"worker-{worker_id}"
    operation = _clean(params.get("operation_type")) or "工资"
    return f"wage-{work_date.isoformat()}-{worker_key}-{operation}"


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


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
