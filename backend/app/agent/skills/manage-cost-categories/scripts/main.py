"""成本分类管理 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills import clear_category_cache
from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.schemas.cost_category import CostCategoryCreate
from app.services import cost_category_service


class ManageCostCategoriesSkill(Skill):
    """创建或删除账务分类。"""

    def name(self) -> str:
        return "manage_cost_categories"

    def description(self) -> str:
        return "创建或删除农场账务分类，删除系统默认分类会被拒绝。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "操作：create/delete"},
                "category_id": {
                    "type": "integer",
                    "description": "分类 ID，删除时必填",
                },
                "name": {"type": "string", "description": "分类名称"},
                "type": {"type": "string", "description": "分类类型 cost/income"},
                "icon": {"type": "string", "description": "图标名称"},
                "sort_order": {"type": "integer", "description": "排序值"},
            },
            "required": ["action"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": ["cost_categories"],
            "cache_invalidation": ["cost_summary", "cost_analytics", "get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["action", "category_id", "name"],
                "changed_fields": ["type", "icon", "sort_order"],
                "editable_fields": [
                    "action",
                    "category_id",
                    "name",
                    "type",
                    "icon",
                    "sort_order",
                ],
                "risk_notes": ["删除分类会影响后续记账分类选择。"],
            },
            "evaluation_tags": ["write", "cost_category"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "管理账务分类")
        if context_error:
            return context_error
        action = str(params.get("action") or "create").strip()
        db = SessionLocal()
        try:
            if action == "create":
                name = _clean(params.get("name"))
                if not name:
                    return SkillResult(
                        status=ResultStatus.NEED_CLARIFY, reply="创建分类需要名称。"
                    )
                data = CostCategoryCreate(
                    name=name,
                    type=_clean(params.get("type")) or "cost",
                    icon=_clean(params.get("icon")) or "tag",
                    sort_order=int(params.get("sort_order") or 0),
                )
                category = cost_category_service.create_category(db, data, farm_id)
                clear_category_cache(farm_id)
                return SkillResult(
                    status=ResultStatus.SUCCESS,
                    reply=f"已创建分类：#{category.id} {category.name}。",
                )
            if action == "delete":
                category_id = params.get("category_id")
                if not category_id:
                    return SkillResult(
                        status=ResultStatus.NEED_CLARIFY,
                        reply="删除分类需要 category_id。",
                    )
                cost_category_service.delete_category(db, int(category_id), farm_id)
                clear_category_cache(farm_id)
                return SkillResult(
                    status=ResultStatus.SUCCESS, reply=f"已删除分类 #{category_id}。"
                )
            return SkillResult(
                status=ResultStatus.FAILED,
                reply="管理分类失败：action 必须是 create 或 delete。",
            )
        except Exception as exc:
            return SkillResult(status=ResultStatus.FAILED, reply=f"管理分类失败：{exc}")
        finally:
            db.close()


def _clean(value) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None
