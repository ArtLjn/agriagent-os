"""种植周期查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.infra.skill_cache import cached
from app.models.cycle import CropCycle
from app.services import farm_context_service


class CropCycleSkill(Skill):
    def name(self) -> str:
        return "get_crop_cycle_info"

    def description(self) -> str:
        return (
            "查询种植周期的详细信息。当用户问茬口状态、当前阶段、"
            "周期进度、茬口详情、西瓜长到哪了时，调用此工具获取真实数据。"
            "需要提供周期 ID。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "integer", "description": "种植周期 ID"},
            },
            "required": [],
        }

    @cached(ttl_seconds=600, key_fn=lambda p: f"cycle:{p.get('cycle_id')}")
    async def execute(self, params: dict, context) -> SkillResult:
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
