"""成本趋势分析操作。"""

from collections import defaultdict
from datetime import datetime, timedelta

from skillify.models.schemas import ResultStatus, SkillResult

from app.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.models.cost import CostRecord


async def analyze_cost(params: dict, context) -> SkillResult:
    farm_id, context_error = require_farm_context(context, "分析收支趋势")
    if context_error:
        return context_error
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    if not date_from or not date_to:
        return SkillResult(
            status=ResultStatus.NEED_CLARIFY,
            reply="分析收支趋势需要 date_from 和 date_to。",
        )
    compare_period = params.get("compare_period", "none")
    db = SessionLocal()
    try:
        current = _query_period(db, farm_id, date_from, date_to)
        lines = [f"收支分析 ({date_from} 至 {date_to})："]
        lines.extend(_format_period(current, "本期"))
        if compare_period != "none":
            prev_from, prev_to = _calc_compare_range(date_from, date_to, compare_period)
            previous = _query_period(db, farm_id, prev_from, prev_to)
            lines.extend(_format_period(previous, "对比期"))
            lines.extend(_format_comparison(current, previous))
        return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
    finally:
        db.close()


def _query_period(db, farm_id, date_from, date_to):
    records = (
        db.query(CostRecord)
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_date >= date_from,
            CostRecord.record_date <= date_to,
        )
        .all()
    )
    cost = sum(
        float(record.amount) for record in records if record.record_type == "cost"
    )
    income = sum(
        float(record.amount) for record in records if record.record_type == "income"
    )
    by_category = defaultdict(lambda: {"cost": 0, "income": 0})
    for record in records:
        by_category[record.category][record.record_type] += float(record.amount)
    return {
        "cost": cost,
        "income": income,
        "net": income - cost,
        "count": len(records),
        "by_category": dict(by_category),
    }


def _format_period(data, label):
    lines = [
        f"  {label}: 支出 {data['cost']:.2f} 元, "
        f"收入 {data['income']:.2f} 元, 净 {data['net']:.2f} 元 "
        f"({data['count']} 笔)",
    ]
    top_cost = sorted(
        [
            (key, value["cost"])
            for key, value in data["by_category"].items()
            if value["cost"] > 0
        ],
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    if top_cost:
        lines.append(
            "    支出TOP3: "
            + ", ".join(f"{key}({value:.0f})" for key, value in top_cost)
        )
    return lines


def _calc_compare_range(date_from, date_to, compare_period):
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


def _format_comparison(current, previous):
    return [
        "  对比变化：",
        f"    支出变化: {_pct_change(current['cost'], previous['cost'])}",
        f"    收入变化: {_pct_change(current['income'], previous['income'])}",
    ]


def _pct_change(current, previous) -> str:
    if previous == 0:
        return "无数据"
    pct = (current - previous) / previous * 100
    return f"{'+' if pct >= 0 else ''}{pct:.1f}%"
