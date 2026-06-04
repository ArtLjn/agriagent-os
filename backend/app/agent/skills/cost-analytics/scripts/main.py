"""全局成本分析 Skill — 跨周期收支趋势分析。"""

from collections import defaultdict
from datetime import datetime, timedelta

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.agent.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.infra.skill_cache import cached
from app.models.cost import CostRecord


class CostAnalyticsSkill(Skill):
    """跨周期收支趋势分析 Skill，支持同比环比对比。"""

    def name(self) -> str:
        return "get_cost_analytics"

    def description(self) -> str:
        return (
            "分析农场收支趋势与对比。当用户问收支趋势、比去年花了多少、"
            "比上月赚了多少、成本分析、同比环比时，调用此工具获取趋势数据。"
            "支持按月、去年同期对比。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "date_from": {
                    "type": "string",
                    "description": "分析开始日期 YYYY-MM-DD",
                },
                "date_to": {
                    "type": "string",
                    "description": "分析结束日期 YYYY-MM-DD",
                },
                "compare_period": {
                    "type": "string",
                    "description": (
                        "对比周期: none(不对比)/last_month(上月)/last_year(去年同期)"
                    ),
                    "default": "none",
                },
            },
            "required": ["date_from", "date_to"],
        }

    @cached(ttl_seconds=300)
    async def execute(self, params: dict, context) -> SkillResult:
        farm_id, context_error = require_farm_context(context, "分析收支趋势")
        if context_error:
            return context_error
        date_from = params["date_from"]
        date_to = params["date_to"]
        compare_period = params.get("compare_period", "none")

        db = SessionLocal()
        try:
            current = self._query_period(db, farm_id, date_from, date_to)
            lines = [f"收支分析 ({date_from} 至 {date_to})："]
            lines.extend(self._format_period(current, "本期"))

            if compare_period != "none":
                prev_from, prev_to = self._calc_compare_range(
                    date_from, date_to, compare_period
                )
                previous = self._query_period(db, farm_id, prev_from, prev_to)
                lines.extend(self._format_period(previous, "对比期"))
                lines.extend(self._format_comparison(current, previous))

            return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
        finally:
            db.close()

    def _query_period(self, db, farm_id, date_from, date_to):
        records = (
            db.query(CostRecord)
            .filter(
                CostRecord.farm_id == farm_id,
                CostRecord.record_date >= date_from,
                CostRecord.record_date <= date_to,
            )
            .all()
        )
        cost = sum(float(r.amount) for r in records if r.record_type == "cost")
        income = sum(float(r.amount) for r in records if r.record_type == "income")

        by_category = defaultdict(lambda: {"cost": 0, "income": 0})
        for r in records:
            by_category[r.category][r.record_type] += float(r.amount)

        return {
            "cost": cost,
            "income": income,
            "net": income - cost,
            "count": len(records),
            "by_category": dict(by_category),
        }

    def _format_period(self, data, label):
        lines = [
            f"  {label}: 支出 {data['cost']:.2f} 元, "
            f"收入 {data['income']:.2f} 元, "
            f"净 {data['net']:.2f} 元 ({data['count']} 笔)",
        ]
        if data["by_category"]:
            top_cost = sorted(
                [
                    (k, v["cost"])
                    for k, v in data["by_category"].items()
                    if v["cost"] > 0
                ],
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            if top_cost:
                lines.append(
                    "    支出TOP3: " + ", ".join(f"{k}({v:.0f})" for k, v in top_cost)
                )
        return lines

    def _calc_compare_range(self, date_from, date_to, compare_period):
        df = datetime.strptime(date_from, "%Y-%m-%d").date()
        dt = datetime.strptime(date_to, "%Y-%m-%d").date()
        days = (dt - df).days + 1

        if compare_period == "last_month":
            prev_df = df - timedelta(days=days)
            prev_dt = df - timedelta(days=1)
        elif compare_period == "last_year":
            prev_df = df.replace(year=df.year - 1)
            prev_dt = dt.replace(year=dt.year - 1)
        else:
            prev_df, prev_dt = df, dt

        return prev_df.isoformat(), prev_dt.isoformat()

    def _format_comparison(self, current, previous):
        if previous["cost"] == 0:
            cost_change = "无数据"
        else:
            pct = (current["cost"] - previous["cost"]) / previous["cost"] * 100
            cost_change = f"{'+' if pct >= 0 else ''}{pct:.1f}%"

        if previous["income"] == 0:
            income_change = "无数据"
        else:
            pct = (current["income"] - previous["income"]) / previous["income"] * 100
            income_change = f"{'+' if pct >= 0 else ''}{pct:.1f}%"

        return [
            "  对比变化：",
            f"    支出变化: {cost_change}",
            f"    收入变化: {income_change}",
        ]
