"""茬口域聚合 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel

from .create_cycle import create_cycle
from .delete_cycle import delete_cycle
from .query_cycle_info import query_cycle_info
from .query_cycles import query_cycles
from .update_cycle import update_cycle


class ManageCropCycleSkill(Skill):
    """统一茬口业务能力 Skill。"""

    def name(self) -> str:
        return "manage_crop_cycle"

    def description(self) -> str:
        return (
            "管理农场种植茬口。通过 operation 选择 create_cycle、query_cycles、"
            "query_cycle_info、update_cycle、update_stage 或 delete_cycle，支持"
            "创建种植周期、查询列表和详情、调整日期阶段状态，以及删除茬口。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": (
                        "操作类型：create_cycle、query_cycles、query_cycle_info、"
                        "update_cycle、update_stage、delete_cycle"
                    ),
                    "enum": [
                        "create_cycle",
                        "query_cycles",
                        "query_cycle_info",
                        "update_cycle",
                        "update_stage",
                        "delete_cycle",
                    ],
                },
                "cycle_id": {"type": "integer", "description": "茬口 ID。"},
                "crop_name": {
                    "type": "string",
                    "description": "作物名称，如玉米、辣椒、西瓜。",
                },
                "cycle_name": {
                    "type": "string",
                    "description": "茬口名称，如夏季玉米，用于定位已有茬口。",
                },
                "season": {"type": "string", "description": "季节，如春季、秋季。"},
                "start_date": {
                    "type": "string",
                    "description": "开始日期 YYYY-MM-DD。",
                },
                "field_name": {"type": "string", "description": "地块名称。"},
                "name": {"type": "string", "description": "新的茬口名称。"},
                "area": {"type": "number", "description": "面积，亩。"},
                "status": {
                    "type": "string",
                    "description": "状态 active、planned 或 finished。",
                },
                "status_filter": {
                    "type": "string",
                    "description": "列表查询状态过滤 active、planned 或 finished。",
                },
                "current_stage": {
                    "type": "string",
                    "description": "当前阶段名称。",
                },
                "stage": {"type": "string", "description": "当前阶段名称别名。"},
                "note": {"type": "string", "description": "批次备注。"},
                "batch_note": {"type": "string", "description": "批次备注。"},
                "current_cycle_id": {
                    "type": "integer",
                    "description": "上下文中的当前茬口 ID。",
                },
                "context_cycle_id": {
                    "type": "integer",
                    "description": "上下文补齐的茬口 ID。",
                },
                "limit": {"type": "integer", "description": "列表返回数量。"},
            },
            "required": ["operation"],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "domain": "crop",
            "capability": "manage_crop_cycle",
            "context_dependencies": [
                "farm",
                "active_cycles",
                "crop_cycles",
                "crop_templates",
            ],
            "cache_invalidation": ["crop_cycle", "get_farm_status"],
            "confirmation_schema": {
                "target_fields": ["cycle_id", "cycle_name", "crop_name"],
                "changed_fields": ["operation", "start_date", "deleted"],
                "inferred_fields": ["crop_name", "cycle_name", "current_context"],
                "editable_fields": [
                    "operation",
                    "cycle_id",
                    "cycle_name",
                    "crop_name",
                    "start_date",
                    "season",
                    "name",
                    "area",
                    "status",
                    "current_stage",
                    "note",
                ],
                "risk_notes": [
                    "修改开始日期会同步重算该茬口所有阶段起止日期。",
                    "删除茬口会级联删除阶段、农事日志、成本记录和种植单元。",
                ],
            },
            "evaluation_tags": ["crop_cycle", "crop", "production"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        operation = str(params.get("operation") or "").strip()
        handlers = {
            "create_cycle": create_cycle,
            "query_cycles": query_cycles,
            "query_cycle_info": query_cycle_info,
            "update_cycle": update_cycle,
            "update_stage": update_cycle,
            "delete_cycle": delete_cycle,
        }
        handler = handlers.get(operation)
        if handler is None:
            return SkillResult(
                status=ResultStatus.NEED_CLARIFY,
                reply="请说明要新建、查询列表、查看详情、修改还是删除茬口。",
            )
        return await handler(params, context)
