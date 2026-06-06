"""结算人工付款 Skill。"""

from datetime import date
from decimal import Decimal, InvalidOperation

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.services import planting_service


class SettleLaborPaymentSkill(Skill):
    """结算或部分支付人工。"""

    def name(self) -> str:
        return "settle_labor_payment"

    def description(self) -> str:
        return (
            "结算或部分支付未付人工，支持按工人、茬口、作业单和日期范围筛选，需确认。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "worker": {"type": "string", "description": "工人姓名"},
                "amount": {
                    "type": "number",
                    "description": "本次支付金额，不传表示全额结清",
                },
                "cycle_id": {"type": "integer", "description": "茬口 ID"},
                "work_order_id": {"type": "integer", "description": "作业单 ID"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
            },
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": [
                "workers",
                "unpaid_labor",
                "operation_work_orders",
            ],
            "cache_invalidation": ["cost_analytics", "cost_summary", "get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["worker", "cycle_id", "work_order_id"],
                "changed_fields": ["amount"],
                "inferred_fields": ["worker", "affected_entries"],
                "editable_fields": [
                    "worker",
                    "amount",
                    "cycle_id",
                    "work_order_id",
                    "start_date",
                    "end_date",
                ],
                "risk_notes": ["确认后会增加人工已付金额。"],
            },
            "evaluation_tags": ["write", "labor", "settlement"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "结算人工")
        if context_error:
            return context_error
        db = SessionLocal()
        try:
            result = planting_service.settle_labor_payment(
                db,
                farm_id=farm_id,
                amount=_to_decimal(params.get("amount")),
                worker_name=_clean(params.get("worker") or params.get("worker_name")),
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
        except Exception as exc:
            return SkillResult(status=ResultStatus.FAILED, reply=f"结算人工失败：{exc}")
        finally:
            db.close()


def _to_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


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
