"""作物模板查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.services import crop_service


class GetCropTemplatesSkill(Skill):
    """查询作物模板。"""

    def name(self) -> str:
        return "get_crop_templates"

    def description(self) -> str:
        return "查询农场作物模板及其生长阶段，用于查看有哪些作物模板可用于创建茬口。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "返回数量，默认 100"}
            },
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "context_dependencies": ["farm", "crop_templates"],
            "evaluation_tags": ["read", "crop_template"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "查询作物模板")
        if context_error:
            return context_error
        db = SessionLocal()
        try:
            limit = int(params.get("limit") or 100)
            templates = crop_service.get_crop_templates(db, farm_id, limit=limit)
            if not templates:
                return SkillResult(status=ResultStatus.SUCCESS, reply="暂无作物模板。")
            lines = ["作物模板："]
            for template in templates:
                variety = f"（{template.variety}）" if template.variety else ""
                stages = sorted(template.stages, key=lambda stage: stage.order_index)
                stage_text = "、".join(stage.name for stage in stages) or "无阶段"
                lines.append(f"- #{template.id} {template.name}{variety}：{stage_text}")
            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"查询作物模板失败：{exc}"
            )
        finally:
            db.close()
