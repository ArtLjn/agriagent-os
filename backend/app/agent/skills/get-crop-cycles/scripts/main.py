"""茬口列表查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.agent.skills.metadata import SkillPermissionLevel, SkillRiskLevel
from app.core.database import SessionLocal
from app.services import cycle_service


class GetCropCyclesSkill(Skill):
    """查询农场茬口列表。"""

    def name(self) -> str:
        return "get_crop_cycles"

    def description(self) -> str:
        return "查询农场茬口列表，适合回答我的茬口、有哪些茬口、种植批次列表。"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "按状态过滤：active、planned 或 finished；不传则返回全部。",
                },
                "limit": {"type": "integer", "description": "返回数量，默认 100。"},
            },
            "required": [],
        }

    def metadata(self) -> dict:
        return {
            "permission_level": SkillPermissionLevel.READ,
            "risk_level": SkillRiskLevel.LOW,
            "context_dependencies": ["farm", "crop_cycles"],
            "evaluation_tags": ["read", "crop_cycle", "list"],
        }

    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "查询茬口列表")
        if context_error:
            return context_error
        db = SessionLocal()
        try:
            limit = int(params.get("limit") or 100)
            status = params.get("status")
            cycles = cycle_service.get_crop_cycles(db, farm_id=farm_id, limit=limit)
            if status:
                cycles = [cycle for cycle in cycles if cycle.status == status]
            if not cycles:
                return SkillResult(status=ResultStatus.SUCCESS, reply="暂无茬口。")

            lines = ["茬口列表："]
            for cycle in cycles:
                lines.append(_format_cycle(cycle))
            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        except Exception as exc:
            return SkillResult(
                status=ResultStatus.FAILED, reply=f"查询茬口列表失败：{exc}"
            )
        finally:
            db.close()


def _format_cycle(cycle) -> str:
    template_name = getattr(getattr(cycle, "crop_template", None), "name", "未知作物")
    current = next((stage for stage in cycle.stages if stage.is_current), None)
    stage_text = current.name if current else "未知阶段"
    area_text = f"，{cycle.total_area_mu}亩" if cycle.total_area_mu is not None else ""
    field_text = f"，地块：{cycle.field_name}" if cycle.field_name else ""
    season_text = f"，{cycle.season}" if cycle.season else ""
    return (
        f"- #{cycle.id} {cycle.name}（{template_name}，{cycle.status}，"
        f"{stage_text}，开始 {cycle.start_date}{season_text}{area_text}{field_text}）"
    )
