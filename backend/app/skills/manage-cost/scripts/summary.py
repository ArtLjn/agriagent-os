"""成本汇总查询操作。"""

from collections import defaultdict

from skillify.models.schemas import ResultStatus, SkillResult

from app.skills.context import require_farm_context
from app.core.database import SessionLocal
from app.models.cost import CostRecord


async def query_summary(params: dict, context) -> SkillResult:
    farm_id, context_error = require_farm_context(context, "查询收支汇总")
    if context_error:
        return context_error
    db = SessionLocal()
    try:
        query = db.query(CostRecord).filter(CostRecord.farm_id == farm_id)
        query = _apply_summary_filters(query, params)
        records = query.order_by(CostRecord.record_date.desc()).all()
        if not records:
            scope = "该周期" if params.get("cycle_id") else "全部"
            return SkillResult(
                status=ResultStatus.SUCCESS,
                reply=f"{scope}暂无成本或收入记录。",
            )
        group_by = params.get("group_by", "none")
        if group_by == "category":
            reply = _group_by_category(records)
        elif group_by == "month":
            reply = _group_by_month(records)
        else:
            reply = _simple_summary(records)
        return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
    finally:
        db.close()


def _apply_summary_filters(query, params: dict):
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


def _simple_summary(records: list) -> str:
    total_cost = sum(float(r.amount) for r in records if r.record_type == "cost")
    total_income = sum(float(r.amount) for r in records if r.record_type == "income")
    lines = [
        "收支汇总：",
        f"  总成本：{total_cost:.2f} 元",
        f"  总收入：{total_income:.2f} 元",
        f"  净利润：{total_income - total_cost:.2f} 元",
        "  明细：",
    ]
    for record in records[:20]:
        lines.append(
            f"    {record.record_date}: {record.record_type} - "
            f"{record.category} {float(record.amount):.2f} 元 "
            f"({record.note or '无备注'})"
        )
    if len(records) > 20:
        lines.append(f"    ... 共 {len(records)} 条记录，仅显示前 20 条")
    return "\n".join(lines)


def _group_by_category(records: list) -> str:
    groups = defaultdict(lambda: {"cost": 0.0, "income": 0.0})
    for record in records:
        groups[record.category][record.record_type] += float(record.amount)
    lines = ["按分类汇总："]
    for category, data in sorted(groups.items()):
        lines.append(
            f"  {category}: 成本 {data['cost']:.2f} 元, "
            f"收入 {data['income']:.2f} 元, "
            f"净利润 {data['income'] - data['cost']:.2f} 元"
        )
    total_cost = sum(data["cost"] for data in groups.values())
    total_income = sum(data["income"] for data in groups.values())
    lines.append(
        f"  合计: 成本 {total_cost:.2f} 元, 收入 {total_income:.2f} 元, "
        f"净利润 {total_income - total_cost:.2f} 元"
    )
    return "\n".join(lines)


def _group_by_month(records: list) -> str:
    groups = defaultdict(lambda: {"cost": 0.0, "income": 0.0})
    for record in records:
        groups[str(record.record_date)[:7]][record.record_type] += float(record.amount)
    lines = ["按月汇总："]
    for month, data in sorted(groups.items()):
        lines.append(
            f"  {month}: 成本 {data['cost']:.2f} 元, "
            f"收入 {data['income']:.2f} 元, "
            f"净利润 {data['income'] - data['cost']:.2f} 元"
        )
    return "\n".join(lines)
