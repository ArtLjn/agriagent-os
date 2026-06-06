"""查询未付人工 Skill。"""

from datetime import date
from decimal import Decimal

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.services import planting_read_service


class GetLaborPayablesSkill(Skill):
    """查询未付人工明细。"""

    def name(self) -> str:
        return "get_labor_payables"

    def description(self) -> str:
        return "查询未付人工，支持按工人、茬口、作业单、日期范围和农场筛选。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "worker": {"type": "string", "description": "工人姓名"},
                "cycle_id": {"type": "integer", "description": "茬口 ID"},
                "cycle_name": {"type": "string", "description": "茬口名称"},
                "work_order_id": {"type": "integer", "description": "作业单 ID"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "limit": {"type": "integer", "description": "最多返回条数"},
            },
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "context_dependencies": ["workers", "unpaid_labor", "crop_cycles"],
            "cache_invalidation": [],
            "confirmation_schema": {},
            "evaluation_tags": ["read", "labor", "payable"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "查询未付人工")
        if context_error:
            return context_error
        db = SessionLocal()
        try:
            entries = planting_read_service.list_labor_payables(
                db,
                farm_id=farm_id,
                worker_name=_clean(params.get("worker")),
                cycle_id=params.get("cycle_id"),
                cycle_name=_clean(params.get("cycle_name")),
                work_order_id=params.get("work_order_id"),
                start_date=_parse_date(params.get("start_date")),
                end_date=_parse_date(params.get("end_date")),
                limit=int(params.get("limit") or 50),
            )
            if not entries:
                return SkillResult(
                    status=ResultStatus.SUCCESS, reply="未找到未付人工。"
                )
            total_payable = sum(
                (entry.payable_amount for entry in entries), Decimal("0")
            )
            total_paid = sum((entry.paid_amount for entry in entries), Decimal("0"))
            total_unpaid = sum((entry.unpaid_amount for entry in entries), Decimal("0"))
            lines = [
                f"未付人工汇总：应付{total_payable}元，已付{total_paid}元，未付{total_unpaid}元"
            ]
            for entry in entries:
                order = entry.work_order
                worker_name = (
                    entry.worker.name if entry.worker else f"工人{entry.worker_id}"
                )
                lines.append(
                    f"- {worker_name}｜作业单#{entry.work_order_id} "
                    f"{order.operation_date if order else ''} "
                    f"{order.operation_type if order else ''}｜"
                    f"应付{entry.payable_amount}元，已付{entry.paid_amount}元，"
                    f"未付{entry.unpaid_amount}元"
                )
            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"查询未付人工失败：{exc}"
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
