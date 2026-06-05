"""查询农事作业单 Skill。"""

from datetime import date

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.services import planting_read_service


class GetOperationWorkOrdersSkill(Skill):
    """查询农事作业单和付款摘要。"""

    def name(self) -> str:
        return "get_operation_work_orders"

    def description(self) -> str:
        return (
            "查询农事作业单，支持按茬口、棚/地块、作业类型、工人、日期范围、"
            "付款状态筛选，返回日期、范围、工人和付款摘要。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "integer", "description": "茬口 ID"},
                "cycle_name": {"type": "string", "description": "茬口名称"},
                "unit_id": {"type": "integer", "description": "种植单元 ID"},
                "unit_name": {"type": "string", "description": "棚/地块名称"},
                "operation_type": {"type": "string", "description": "作业类型"},
                "worker": {"type": "string", "description": "工人姓名"},
                "start_date": {"type": "string", "description": "开始日期 YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "结束日期 YYYY-MM-DD"},
                "payment_status": {
                    "type": "string",
                    "description": "付款状态：unpaid、partial、settled、has_unpaid",
                },
                "limit": {"type": "integer", "description": "最多返回条数"},
            },
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "context_dependencies": ["crop_cycles", "planting_units", "workers"],
            "cache_invalidation": [],
            "confirmation_schema": {},
            "evaluation_tags": ["read", "operation_work_order", "labor"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
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
                start_date=_parse_date(params.get("start_date")),
                end_date=_parse_date(params.get("end_date")),
                payment_status=_clean(params.get("payment_status")),
                limit=int(params.get("limit") or 20),
            )
            if not items:
                return SkillResult(status=ResultStatus.SUCCESS, reply="未找到匹配的农事作业单。")
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
            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=f"查询农事作业单失败：{exc}",
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
