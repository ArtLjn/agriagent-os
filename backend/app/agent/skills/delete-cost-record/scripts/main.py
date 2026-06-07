"""删除账务记录 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.services import cost_service


class DeleteCostRecordSkill(Skill):
    """软删除账务记录。"""

    def name(self) -> str:
        return "delete_cost_record"

    def description(self) -> str:
        return "删除或撤销一条账务记录。执行后软删除记录并刷新账务统计。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "record_id": {"type": "integer", "description": "账务记录 ID"}
            },
            "required": ["record_id"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": ["cost_records"],
            "cache_invalidation": [
                "cost_analytics",
                "cost_summary",
                "get_farm_status",
            ],
            "confirmation_schema": {
                "target_fields": ["record_id"],
                "changed_fields": ["deleted_at"],
                "editable_fields": ["record_id"],
                "risk_notes": ["确认后会软删除该账务记录，并影响统计结果。"],
            },
            "evaluation_tags": ["write", "cost", "delete"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "删除账务记录")
        if context_error:
            return context_error
        record_id = params.get("record_id")
        if not record_id:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY, reply="删除账务记录需要 record_id。"
            )
        db = SessionLocal()
        try:
            record = cost_service.delete_record(db, int(record_id), farm_id)
            if record is None:
                return SkillResult(
                    status=ResultStatus.FAILED, reply="删除账务记录失败：记录不存在。"
                )
            return SkillResult(
                status=ResultStatus.SUCCESS, reply=f"已删除账务记录 #{record.id}。"
            )
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"删除账务记录失败：{exc}"
            )
        finally:
            db.close()
