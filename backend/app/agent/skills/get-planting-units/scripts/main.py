"""种植单元查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.services import planting_service


class GetPlantingUnitsSkill(Skill):
    """查询棚、地块等种植单元。"""

    def name(self) -> str:
        return "get_planting_units"

    def description(self) -> str:
        return "查询农场种植单元、棚、地块或区域，可按茬口 ID 过滤。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {
                    "type": "integer",
                    "description": "茬口 ID，可选；提供后只查询该茬口下的单元。",
                }
            },
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "context_dependencies": ["farm", "crop_cycles", "planting_units"],
            "evaluation_tags": ["read", "planting_unit"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "查询种植单元")
        if context_error:
            return context_error
        db = SessionLocal()
        try:
            cycle_id = params.get("cycle_id")
            units = planting_service.list_units(db, farm_id, cycle_id=cycle_id)
            if not units:
                return SkillResult(status=ResultStatus.SUCCESS, reply="暂无种植单元。")
            lines = ["种植单元："]
            for unit in units:
                area = f"，{unit.area_mu}亩" if unit.area_mu is not None else ""
                planted = f"，定植 {unit.planted_date}" if unit.planted_date else ""
                note = f"，备注：{unit.note}" if unit.note else ""
                lines.append(
                    f"- #{unit.id} {unit.name}（茬口 #{unit.cycle_id}{area}{planted}"
                    f"，状态 {unit.status}{note}）"
                )
            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"查询种植单元失败：{exc}"
            )
        finally:
            db.close()
