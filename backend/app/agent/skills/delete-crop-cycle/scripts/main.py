"""删除茬口 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.services import cycle_service


class DeleteCropCycleSkill(Skill):
    """高风险删除茬口。"""

    def name(self) -> str:
        return "delete_crop_cycle"

    def description(self) -> str:
        return "删除指定茬口，并级联删除其阶段、农事日志、成本记录和种植单元。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {"cycle_id": {"type": "integer", "description": "茬口 ID"}},
            "required": ["cycle_id"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.HIGH,
            "context_dependencies": ["crop_cycles", "farm_logs", "cost_records"],
            "cache_invalidation": [
                "crop_cycle",
                "farm_logs",
                "cost_summary",
                "cost_analytics",
                "get_farm_status",
            ],
            "confirmation_schema": {
                "target_fields": ["cycle_id"],
                "changed_fields": ["deleted"],
                "editable_fields": ["cycle_id"],
                "risk_notes": [
                    "删除茬口会级联删除阶段、农事日志、成本记录和种植单元。"
                ],
            },
            "evaluation_tags": ["write", "crop_cycle", "delete"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "删除茬口")
        if context_error:
            return context_error
        cycle_id = params.get("cycle_id")
        if not cycle_id:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY, reply="删除茬口需要 cycle_id。"
            )
        db = SessionLocal()
        try:
            cycle_service.delete_crop_cycle(db, int(cycle_id), farm_id)
            return SkillResult(
                status=ResultStatus.SUCCESS, reply=f"已删除茬口 #{cycle_id}。"
            )
        except Exception as exc:
            return SkillResult(status=ResultStatus.FAILED, reply=f"删除茬口失败：{exc}")
        finally:
            db.close()
