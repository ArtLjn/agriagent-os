"""人工付款聚合 Skill。"""

from datetime import date
from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.models.planting import Worker
from app.schemas.planting import WageSaveRequest, WageUpdateRequest
from app.services import labor_service, planting_read_service, planting_service

_QUERY_OPERATION = "query_payables"
_SETTLE_OPERATION = "settle_payment"
_WAGE_OPERATION = "manage_wage"
_QUERY_FIELDS = {
    "worker",
    "worker_name",
    "cycle_id",
    "cycle_name",
    "work_order_id",
    "start_date",
    "end_date",
    "limit",
}
_SETTLE_FIELDS = {"amount", "scope", "payment_date"}
_WAGE_FIELDS = {
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
}


class ManageLaborPaymentSkill(Skill):
    """管理人工付款：查询未付、结算付款、保存或更新工资记录。"""

    def name(self) -> str:
        return "manage_labor_payment"

    def description(self) -> str:
        return (
            "管理人工付款，支持查询未付人工、结算或补付工资、保存或更新独立工资记录。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": (
                        "操作：query_payables、settle_payment 或 manage_wage。"
                    ),
                    "enum": [_QUERY_OPERATION, _SETTLE_OPERATION, _WAGE_OPERATION],
                },
                "action": {
                    "type": "string",
                    "description": "工资记录操作：save/update。",
                },
                "labor_entry_id": {"type": "integer", "description": "工资记录 ID。"},
                "worker": {"type": "string", "description": "工人姓名。"},
                "worker_id": {"type": "integer", "description": "工人 ID。"},
                "worker_name": {"type": "string", "description": "工人姓名。"},
                "scope": {
                    "type": "string",
                    "description": "结算范围；all_unpaid_labor 表示全部未付人工。",
                },
                "amount": {
                    "type": "number",
                    "description": "本次结算金额，不传表示全额结清。",
                },
                "cycle_id": {"type": "integer", "description": "茬口 ID。"},
                "cycle_name": {"type": "string", "description": "茬口名称。"},
                "work_order_id": {"type": "integer", "description": "作业单 ID。"},
                "operation_type": {
                    "type": "string",
                    "description": "工资作业类型，如采收、装车、整枝打杈。",
                },
                "pay_type": {
                    "type": "string",
                    "description": "计薪方式，如 daily、hourly、piece。",
                },
                "quantity": {
                    "type": "number",
                    "description": "工资数量，如天数/小时/件数。",
                },
                "unit_price": {"type": "number", "description": "工资单价。"},
                "paid_amount": {"type": "number", "description": "工资记录已付金额。"},
                "note": {"type": "string", "description": "工资记录备注。"},
                "work_date": {
                    "type": "string",
                    "description": "作业/工资日期 YYYY-MM-DD；新增工资必填。",
                },
                "start_date": {"type": "string", "description": "查询开始日期。"},
                "end_date": {"type": "string", "description": "查询结束日期。"},
                "limit": {"type": "integer", "description": "查询最多返回条数。"},
                "client_request_id": {
                    "type": "string",
                    "description": "工资记录幂等键。",
                },
            },
            "required": [],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": [
                "workers",
                "unpaid_labor",
                "crop_cycles",
                "operation_work_orders",
            ],
            "cache_invalidation": [
                "cost_analytics",
                "cost_summary",
                "get_farm_status",
            ],
            "confirmation_schema": {
                "target_fields": [
                    "operation",
                    "worker",
                    "worker_name",
                    "labor_entry_id",
                    "work_order_id",
                ],
                "changed_fields": [
                    "amount",
                    "cycle_id",
                    "operation_type",
                    "quantity",
                    "unit_price",
                    "paid_amount",
                    "work_date",
                    "note",
                ],
                "inferred_fields": [
                    "scope",
                    "affected_entries",
                    "client_request_id",
                ],
                "editable_fields": [
                    "operation",
                    "action",
                    "labor_entry_id",
                    "worker",
                    "worker_id",
                    "worker_name",
                    "scope",
                    "amount",
                    "cycle_id",
                    "work_order_id",
                    "operation_type",
                    "pay_type",
                    "quantity",
                    "unit_price",
                    "paid_amount",
                    "work_date",
                    "note",
                ],
                "risk_notes": [
                    "结算会增加人工已付金额；工资记录会同步人工成本账单。"
                ],
            },
            "evaluation_tags": ["read", "write", "labor", "payable", "wage"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "管理人工付款")
        if context_error:
            return context_error

        params = dict(params or {})
        operation = _resolve_operation(params)
        if operation is None:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply=(
                    "请确认是要结算人工工资，还是新增/修改工资记录。"
                    "结算请提供 amount 或 operation=settle_payment；"
                    "记工资请提供 operation=manage_wage。"
                ),
            )

        db = SessionLocal()
        try:
            if operation == _QUERY_OPERATION:
                return _query_payables(db, farm_id, params)
            if operation == _SETTLE_OPERATION:
                return _settle_payment(db, farm_id, params)
            if operation == _WAGE_OPERATION:
                return _manage_wage(db, farm_id, params)
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=(
                    "管理人工付款失败：operation 必须是 query_payables、"
                    "settle_payment 或 manage_wage。"
                ),
            )
        except ValueError as exc:
            return SkillResult(status=ResultStatus.NEED_CLARIFY, reply=str(exc))
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"管理人工付款失败：{exc}"
            )
        finally:
            db.close()


def _resolve_operation(params: dict) -> str | None:
    operation = _clean(params.get("operation"))
    if operation in {_QUERY_OPERATION, _SETTLE_OPERATION, _WAGE_OPERATION}:
        return operation
    if operation:
        return operation

    has_settle_signal = any(params.get(key) not in (None, "") for key in _SETTLE_FIELDS)
    has_wage_signal = any(params.get(key) not in (None, "") for key in _WAGE_FIELDS)
    if has_settle_signal and _only_worker_id_wage_signal(params):
        return _SETTLE_OPERATION
    if has_settle_signal and has_wage_signal:
        return None
    if has_settle_signal:
        return _SETTLE_OPERATION
    if has_wage_signal:
        return _WAGE_OPERATION
    return _QUERY_OPERATION


def _query_payables(db, farm_id: int, params: dict) -> SkillResult:
    entries = planting_read_service.list_labor_payables(
        db,
        farm_id=farm_id,
        worker_name=_clean(params.get("worker") or params.get("worker_name")),
        cycle_id=params.get("cycle_id"),
        cycle_name=_clean(params.get("cycle_name")),
        work_order_id=params.get("work_order_id"),
        start_date=_parse_date(params.get("start_date")),
        end_date=_parse_date(params.get("end_date")),
        limit=int(params.get("limit") or 50),
    )
    if not entries:
        return SkillResult(status=ResultStatus.SUCCESS, reply="未找到未付人工。")
    total_payable = sum((entry.payable_amount for entry in entries), Decimal("0"))
    total_paid = sum((entry.paid_amount for entry in entries), Decimal("0"))
    total_unpaid = sum((entry.unpaid_amount for entry in entries), Decimal("0"))
    lines = [
        f"未付人工汇总：应付{total_payable}元，已付{total_paid}元，未付{total_unpaid}元"
    ]
    for entry in entries:
        order = entry.work_order
        worker_name = entry.worker.name if entry.worker else f"工人{entry.worker_id}"
        lines.append(
            f"- {worker_name}｜作业单#{entry.work_order_id} "
            f"{order.operation_date if order else ''} "
            f"{order.operation_type if order else ''}｜"
            f"应付{entry.payable_amount}元，已付{entry.paid_amount}元，"
            f"未付{entry.unpaid_amount}元"
        )
    return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))


def _settle_payment(db, farm_id: int, params: dict) -> SkillResult:
    result = planting_service.settle_labor_payment(
        db,
        farm_id=farm_id,
        amount=_to_decimal(params.get("amount")),
        worker_name=_settlement_worker_name(db, farm_id, params),
        cycle_id=params.get("cycle_id"),
        work_order_id=params.get("work_order_id"),
        start_date=_parse_date(params.get("start_date")),
        end_date=_parse_date(params.get("end_date")),
    )
    lines = [
        f"已结算人工{result['paid_amount']}元，"
        f"剩余未付{result['remaining_unpaid']}元。"
    ]
    for item in result["affected_entries"]:
        lines.append(
            f"- {item['worker_name']} 作业单#{item['work_order_id']}："
            f"本次支付{item['paid_amount']}元，"
            f"剩余{item['remaining_unpaid']}元"
        )
    return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))


def _only_worker_id_wage_signal(params: dict) -> bool:
    wage_keys = {
        key for key in _WAGE_FIELDS if params.get(key) not in (None, "")
    }
    return wage_keys == {"worker_id"}


def _settlement_worker_name(db, farm_id: int, params: dict) -> str | None:
    worker_name = _clean(params.get("worker") or params.get("worker_name"))
    if worker_name:
        return worker_name
    worker_id = params.get("worker_id")
    if worker_id in (None, ""):
        return None
    worker = (
        db.query(Worker)
        .filter(Worker.id == int(worker_id), Worker.farm_id == farm_id)
        .first()
    )
    if worker is None:
        raise ValueError("工人不存在，请提供有效 worker_id。")
    return worker.name


def _manage_wage(db, farm_id: int, params: dict) -> SkillResult:
    action = _clean(params.get("action")) or "save"
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
    return SkillResult(status=ResultStatus.SUCCESS, reply=_format_reply(action, response))


def _build_save_request(params: dict) -> WageSaveRequest:
    worker_id = params.get("worker_id")
    worker_name = _clean(params.get("worker_name") or params.get("worker"))
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
