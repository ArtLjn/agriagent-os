"""工人档案查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.models.planting import Worker
from app.services import planting_service


class GetWorkersSkill(Skill):
    """查询工人档案。"""

    def name(self) -> str:
        return "get_workers"

    def description(self) -> str:
        return "查询工人档案，默认只返回活跃工人，可按需包含已停用/离职工人。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "active_only": {
                    "type": "boolean",
                    "description": "是否只返回活跃工人，默认 true",
                }
            },
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "context_dependencies": ["workers", "unpaid_labor"],
            "cache_invalidation": [],
            "confirmation_schema": {},
            "evaluation_tags": ["read", "worker", "labor"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "查询工人")
        if context_error:
            return context_error
        active_only = params.get("active_only")
        db = SessionLocal()
        try:
            workers = planting_service.list_workers(
                db,
                farm_id,
                active_only=True if active_only is None else bool(active_only),
            )
            if not workers:
                return SkillResult(
                    status=ResultStatus.SUCCESS, reply="当前没有活跃工人。"
                )
            lines = ["当前工人："]
            for worker in workers:
                lines.append(_format_worker(worker))
            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        except Exception as exc:
            return SkillResult(status=ResultStatus.FAILED, reply=f"查询工人失败：{exc}")
        finally:
            db.close()


def _format_worker(worker: Worker) -> str:
    price = worker.default_unit_price
    price_text = f"{price}元" if price is not None else "未设置"
    status_text = "活跃" if worker.status == "active" else "已停用"
    return f"- {worker.name}（{status_text}，{worker.default_pay_type}，默认单价 {price_text}）"
