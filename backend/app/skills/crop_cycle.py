"""种植周期查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.core.skill_cache import cached
from app.models.cycle import CropCycle


class CropCycleSkill(Skill):
    def name(self) -> str:
        return "get_crop_cycle_info"

    def description(self) -> str:
        return "查询指定种植周期的详细信息，包括当前阶段和各阶段安排。触发词: 周期、阶段、茬口"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "integer", "description": "种植周期 ID"},
            },
            "required": ["cycle_id"],
        }

    @cached(ttl_seconds=600, key_fn=lambda p: f"cycle:{p.get('cycle_id')}")
    async def execute(self, params: dict, context) -> SkillResult:
        cycle_id = params["cycle_id"]
        db = SessionLocal()
        try:
            cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id).first()
            if not cycle:
                return SkillResult(status=ResultStatus.SUCCESS, reply=f"未找到 ID 为 {cycle_id} 的种植周期。")

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
                    f"  {stage.name}{current_marker}: {stage.start_date} ~ {stage.end_date} "
                    f"({stage.duration_days} 天) 关键任务：{stage.key_tasks or '无'}"
                )

            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        finally:
            db.close()


skill = CropCycleSkill()
