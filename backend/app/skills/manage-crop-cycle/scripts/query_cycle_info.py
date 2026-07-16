"""茬口详情查询 operation。"""

from skillify.models.schemas import ResultStatus, SkillResult

from app.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.models.cycle import CropCycle
from app.services import farm_context_service


async def query_cycle_info(params: dict, context) -> SkillResult:
    cycle_id = params.get("cycle_id")
    farm_id, context_error = require_farm_context(context, "查询茬口")
    if context_error:
        return context_error
    db = SessionLocal()
    try:
        if cycle_id is None:
            summary = await farm_context_service.build_summary(db, farm_id=farm_id)
            reply = "未指定茬口 ID，已先返回当前农场状态：\n" + summary
            return SkillResult(status=ResultStatus.SUCCESS, reply=reply)

        cycle = (
            db.query(CropCycle)
            .filter(CropCycle.id == cycle_id, CropCycle.farm_id == farm_id)
            .first()
        )
        if not cycle:
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=f"未找到 ID 为 {cycle_id} 的种植周期。",
            )

        lines = [
            f"茬口：{cycle.name}",
            f"开始日期：{cycle.start_date}",
            f"地块：{cycle.field_name or '未指定'}",
            f"状态：{cycle.status}",
            "阶段安排：",
        ]
        for stage in sorted(cycle.stages, key=lambda s: s.order_index):
            current_marker = " [当前]" if stage.is_current else ""
            lines.append(
                f"  {stage.name}{current_marker}: "
                f"{stage.start_date} ~ {stage.end_date} "
                f"({stage.duration_days}天) "
                f"关键任务：{stage.key_tasks or '无'}"
            )

        return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
    finally:
        db.close()
