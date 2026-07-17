"""茬口列表查询 operation。"""

from skillify.models.schemas import ResultStatus, SkillResult

from app.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.services import cycle_service


async def query_cycles(params: dict, context) -> SkillResult:
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
        return SkillResult(status=ResultStatus.FAILED, reply=f"查询茬口列表失败：{exc}")
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
