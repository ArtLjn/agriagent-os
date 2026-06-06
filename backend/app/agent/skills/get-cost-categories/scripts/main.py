"""成本分类查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.services import cost_category_service


class GetCostCategoriesSkill(Skill):
    """查询成本/收入分类。"""

    def name(self) -> str:
        return "get_cost_categories"

    def description(self) -> str:
        return "查询农场账务分类，包括支出分类和收入分类。"

    def parameters_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "context_dependencies": ["cost_categories"],
            "evaluation_tags": ["read", "cost_category"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "查询账务分类")
        if context_error:
            return context_error
        db = SessionLocal()
        try:
            categories = cost_category_service.get_categories(db, farm_id)
            if not categories:
                return SkillResult(status=ResultStatus.SUCCESS, reply="暂无账务分类。")
            lines = ["账务分类："]
            for category in categories:
                type_text = "收入" if category.type == "income" else "支出"
                default_text = "默认" if category.is_default else "自定义"
                lines.append(
                    f"- #{category.id} {category.name}（{type_text}，{default_text}）"
                )
            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"查询账务分类失败：{exc}"
            )
        finally:
            db.close()
