"""成本汇总查询 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.core.skill_cache import cached
from app.models.cost import CostRecord


class CostSummarySkill(Skill):
    def name(self) -> str:
        return "get_cycle_cost_summary"

    def description(self) -> str:
        return "查询指定周期的成本与收入汇总。触发词: 成本、收入、利润、收支"

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {"type": "integer", "description": "种植周期 ID"},
            },
            "required": ["cycle_id"],
        }

    @cached(ttl_seconds=300, key_fn=lambda p: f"cost:{p.get('cycle_id')}")
    async def execute(self, params: dict, context) -> SkillResult:
        cycle_id = params["cycle_id"]
        db = SessionLocal()
        try:
            records = db.query(CostRecord).filter(CostRecord.cycle_id == cycle_id).all()
            if not records:
                return SkillResult(status=ResultStatus.SUCCESS, reply="该周期暂无成本或收入记录。")

            total_cost = sum(r.amount for r in records if r.record_type == "cost")
            total_income = sum(r.amount for r in records if r.record_type == "income")
            net = total_income - total_cost

            lines = [
                "周期收支汇总：",
                f"  总成本：{total_cost} 元",
                f"  总收入：{total_income} 元",
                f"  净利润：{net} 元",
                "  明细：",
            ]
            for r in records:
                lines.append(f"    {r.record_date}: {r.record_type} - {r.category} {r.amount} 元 ({r.note or '无备注'})")

            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        finally:
            db.close()
