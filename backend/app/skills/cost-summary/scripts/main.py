"""成本汇总查询 Skill。"""

from collections import defaultdict

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.database import SessionLocal
from app.core.skill_cache import cached
from app.models.cost import CostRecord


class CostSummarySkill(Skill):
    """成本汇总 Skill，支持按周期、日期范围、分类、类型等多维度查询与分组。"""

    def name(self) -> str:
        return "get_cost_summary"

    def description(self) -> str:
        return (
            "查询农场成本与收入汇总，支持按周期、日期范围、分类、记录类型筛选，"
            "并可按分类或月份分组。触发词: 成本、收入、利润、收支"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cycle_id": {
                    "type": "integer",
                    "description": "种植周期 ID（可选，不传则查全部记录）",
                },
                "date_from": {
                    "type": "string",
                    "description": "开始日期 YYYY-MM-DD",
                },
                "date_to": {
                    "type": "string",
                    "description": "结束日期 YYYY-MM-DD",
                },
                "record_type": {
                    "type": "string",
                    "description": "记录类型: cost(支出)/income(收入)/all(全部，默认)",
                    "default": "all",
                },
                "category": {
                    "type": "string",
                    "description": "分类筛选（可选，如'人工'、'化肥'）",
                },
                "group_by": {
                    "type": "string",
                    "description": "分组方式: none(不分组)/category(按分类)/month(按月)，默认none",
                    "default": "none",
                },
            },
            "required": [],
        }

    @cached(
        ttl_seconds=300,
        key_fn=lambda p: f"cost_summary:{hash(str(sorted(p.items())))}",
    )
    async def execute(self, params: dict, context) -> SkillResult:
        """执行成本汇总查询。"""
        farm_id = getattr(context, "farm_id", 1) or 1
        db = SessionLocal()
        try:
            query = db.query(CostRecord).filter(CostRecord.farm_id == farm_id)
            query = self._apply_filters(query, params)
            records = query.order_by(CostRecord.record_date.desc()).all()

            if not records:
                scope = "该周期" if params.get("cycle_id") else "全部"
                return SkillResult(
                    status=ResultStatus.SUCCESS,
                    reply=f"{scope}暂无成本或收入记录。",
                )

            group_by = params.get("group_by", "none")
            if group_by == "category":
                reply = self._group_by_category(records)
            elif group_by == "month":
                reply = self._group_by_month(records)
            else:
                reply = self._simple_summary(records)

            return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
        finally:
            db.close()

    def _apply_filters(self, query, params: dict):
        """应用可选筛选条件。"""
        if params.get("cycle_id"):
            query = query.filter(CostRecord.cycle_id == params["cycle_id"])
        if params.get("date_from"):
            query = query.filter(CostRecord.record_date >= params["date_from"])
        if params.get("date_to"):
            query = query.filter(CostRecord.record_date <= params["date_to"])
        if params.get("record_type") and params["record_type"] != "all":
            query = query.filter(CostRecord.record_type == params["record_type"])
        if params.get("category"):
            query = query.filter(CostRecord.category == params["category"])
        return query

    def _simple_summary(self, records: list) -> str:
        """简单汇总：列出总计与明细。"""
        total_cost = sum(float(r.amount) for r in records if r.record_type == "cost")
        total_income = sum(
            float(r.amount) for r in records if r.record_type == "income"
        )
        net = total_income - total_cost

        lines = [
            "收支汇总：",
            f"  总成本：{total_cost:.2f} 元",
            f"  总收入：{total_income:.2f} 元",
            f"  净利润：{net:.2f} 元",
            "  明细：",
        ]
        for r in records[:20]:
            lines.append(
                f"    {r.record_date}: {r.record_type} - {r.category} "
                f"{float(r.amount):.2f} 元 ({r.note or '无备注'})"
            )
        if len(records) > 20:
            lines.append(f"    ... 共 {len(records)} 条记录，仅显示前 20 条")

        return "\n".join(lines)

    def _group_by_category(self, records: list) -> str:
        """按分类分组汇总。"""
        groups = defaultdict(lambda: {"cost": 0.0, "income": 0.0})
        for r in records:
            groups[r.category][r.record_type] += float(r.amount)

        lines = ["按分类汇总："]
        for category, data in sorted(groups.items()):
            net = data["income"] - data["cost"]
            lines.append(
                f"  {category}: 成本 {data['cost']:.2f} 元, "
                f"收入 {data['income']:.2f} 元, 净利润 {net:.2f} 元"
            )

        total_cost = sum(d["cost"] for d in groups.values())
        total_income = sum(d["income"] for d in groups.values())
        lines.append(
            f"  合计: 成本 {total_cost:.2f} 元, "
            f"收入 {total_income:.2f} 元, "
            f"净利润 {total_income - total_cost:.2f} 元"
        )
        return "\n".join(lines)

    def _group_by_month(self, records: list) -> str:
        """按月分组汇总。"""
        groups = defaultdict(lambda: {"cost": 0.0, "income": 0.0})
        for r in records:
            month = str(r.record_date)[:7]  # YYYY-MM
            groups[month][r.record_type] += float(r.amount)

        lines = ["按月汇总："]
        for month, data in sorted(groups.items()):
            net = data["income"] - data["cost"]
            lines.append(
                f"  {month}: 成本 {data['cost']:.2f} 元, "
                f"收入 {data['income']:.2f} 元, 净利润 {net:.2f} 元"
            )

        total_cost = sum(d["cost"] for d in groups.values())
        total_income = sum(d["income"] for d in groups.values())
        lines.append(
            f"  合计: 成本 {total_cost:.2f} 元, "
            f"收入 {total_income:.2f} 元, "
            f"净利润 {total_income - total_cost:.2f} 元"
        )
        return "\n".join(lines)
