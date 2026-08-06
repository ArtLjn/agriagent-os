"""成本分类管理 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.skills import clear_category_cache
from app.skills.context import require_farm_context
from app.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.shared.database import SessionLocal
from app.domains.finance.cost_category_schemas import CostCategoryCreate
from app.domains.finance import cost_category_service


class ManageCostCategoriesSkill(Skill):
    """查询、创建或删除账务分类。"""

    def name(self) -> str:
        return "manage_cost_categories"

    def description(self) -> str:
        return "查询、创建或删除农场账务分类，删除系统默认分类会被拒绝。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": (
                        "操作：query_categories/create_category/delete_category/"
                        "manage_category"
                    ),
                },
                "action": {
                    "type": "string",
                    "description": "兼容操作：create/delete/query",
                },
                "category_id": {
                    "type": "integer",
                    "description": "分类 ID，删除时必填",
                },
                "name": {"type": "string", "description": "分类名称"},
                "type": {"type": "string", "description": "分类类型 cost/income"},
                "icon": {"type": "string", "description": "图标名称"},
                "sort_order": {"type": "integer", "description": "排序值"},
            },
            "required": [],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.WRITE_CONFIRM,
            "risk_level": SkillRiskLevel.MEDIUM,
            "context_dependencies": ["cost_categories"],
            "cache_invalidation": ["cost_summary", "cost_analytics", "get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["operation", "action", "category_id", "name"],
                "changed_fields": ["type", "icon", "sort_order"],
                "editable_fields": [
                    "action",
                    "operation",
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
        operation = _operation(params)
        db = SessionLocal()
        try:
            if operation == "query_categories":
                return _query_categories(db, farm_id)
            if operation == "create_category":
                return _create_category(db, params, farm_id)
            if operation == "delete_category":
                return _delete_category(db, params, farm_id)
            return SkillResult(
                status=ResultStatus.FAILED,
                reply=(
                    "管理分类失败：operation 必须是 query_categories、"
                    "create_category 或 delete_category。"
                ),
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


def _operation(params: dict) -> str:
    operation = _clean(params.get("operation"))
    action = _clean(params.get("action"))
    if operation == "manage_category":
        operation = None
    if operation:
        return operation
    if action == "delete":
        return "delete_category"
    if action == "query":
        return "query_categories"
    return "create_category"


def _query_categories(db, farm_id: int) -> SkillResult:
    categories = cost_category_service.get_categories(db, farm_id)
    if not categories:
        return SkillResult(status=ResultStatus.SUCCESS, reply="暂无账务分类。")
    lines = ["账务分类："]
    for category in categories:
        type_text = "收入" if category.type == "income" else "支出"
        default_text = "默认" if category.is_default else "自定义"
        lines.append(f"- #{category.id} {category.name}（{type_text}，{default_text}）")
    return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))


def _create_category(db, params: dict, farm_id: int) -> SkillResult:
    name = _clean(params.get("name"))
    if not name:
        return SkillResult(status=ResultStatus.NEED_CLARIFY, reply="创建分类需要名称。")
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


def _delete_category(db, params: dict, farm_id: int) -> SkillResult:
    category_id = params.get("category_id")
    if not category_id:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply="删除分类需要 category_id。",
        )
    cost_category_service.delete_category(db, int(category_id), farm_id)
    clear_category_cache(farm_id)
    return SkillResult(status=ResultStatus.SUCCESS, reply=f"已删除分类 #{category_id}。")
