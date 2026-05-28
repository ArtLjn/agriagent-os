"""农事记录查询 Skill。"""

from datetime import date, timedelta

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.infra.skill_cache import cached
from app.models.log import FarmLog


class FarmLogSkill(Skill):
    def name(self) -> str:
        return "get_recent_farm_logs"

    def description(self) -> str:
        return (
            "查询最近几天的农事操作记录。当用户问最近干了啥、查看农事记录、"
            "最近的操作日志、这几天做了什么农活时，调用此工具获取真实记录。"
            "需要提供周期 ID。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "integer", "description": "种植周期 ID"},
                "days": {
                    "type": "integer",
                    "description": "查询天数（默认 7）",
                    "default": 7,
                },
            },
            "required": ["cycle_id"],
        }

    @cached(
        ttl_seconds=60, key_fn=lambda p: f"logs:{p.get('cycle_id')}:{p.get('days', 7)}"
    )
    async def execute(self, params: dict, context) -> SkillResult:
        cycle_id = params["cycle_id"]
        days = params.get("days", 7)
        db = SessionLocal()
        try:
            since = date.today() - timedelta(days=days)
            logs = (
                db.query(FarmLog)
                .filter(FarmLog.cycle_id == cycle_id, FarmLog.operation_date >= since)
                .order_by(FarmLog.operation_date.desc())
                .limit(20)
                .all()
            )
            if not logs:
                return SkillResult(
                    status=ResultStatus.SUCCESS, reply=f"最近 {days} 天内没有农事记录。"
                )

            lines = [f"最近 {days} 天农事记录（共 {len(logs)} 条）："]
            for log in logs:
                lines.append(
                    f"  {log.operation_date}: "
                    f"{log.operation_type} - {log.note or '无备注'}"
                )

            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        finally:
            db.close()
