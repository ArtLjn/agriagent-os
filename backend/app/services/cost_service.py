import json
import logging
from decimal import Decimal
from datetime import date

from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate, CycleProfit, YearlySummary, CostParseResponse
from app.core.llm import get_llm, llm_invoke_with_breaker, LlmNotConfiguredError

logger = logging.getLogger(__name__)


def create_record(db: Session, record: CostRecordCreate, farm_id: int) -> CostRecord:
    """创建一条成本或收入记录。

    Args:
        db: 数据库会话。
        record: 创建请求数据。
        farm_id: 农场 ID。

    Returns:
        新创建的 CostRecord 实例。
    """
    db_record = CostRecord(
        cycle_id=record.cycle_id,
        record_type=record.record_type,
        category=record.category,
        amount=record.amount,
        record_date=record.record_date,
        note=record.note,
        farm_id=farm_id,
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


def get_records(
    db: Session, farm_id: int, cycle_id: int | None = None, category: str | None = None
) -> list[CostRecord]:
    """查询成本记账记录列表。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        cycle_id: 按种植周期 ID 筛选（可选）。
        category: 按类别筛选（可选）。

    Returns:
        符合条件的 CostRecord 列表，按记录日期倒序排列。
    """
    query = db.query(CostRecord).filter(CostRecord.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(CostRecord.cycle_id == cycle_id)
    if category is not None:
        query = query.filter(CostRecord.category == category)
    return query.order_by(CostRecord.record_date.desc()).all()


def get_cycle_profit(db: Session, cycle_id: int, farm_id: int) -> CycleProfit:
    """计算指定种植周期的利润。

    Args:
        db: 数据库会话。
        cycle_id: 种植周期 ID。
        farm_id: 农场 ID。

    Returns:
        周期利润统计对象。
    """
    records = db.query(CostRecord).filter(CostRecord.cycle_id == cycle_id, CostRecord.farm_id == farm_id).all()
    total_cost = sum(
        (r.amount for r in records if r.record_type == "cost"),
        Decimal("0"),
    )
    total_income = sum(
        (r.amount for r in records if r.record_type == "income"),
        Decimal("0"),
    )
    return CycleProfit(
        cycle_id=cycle_id,
        total_cost=total_cost,
        total_income=total_income,
        net_profit=total_income - total_cost,
    )


def get_yearly_summary(db: Session, year: int, farm_id: int) -> YearlySummary:
    """计算指定年度的收支汇总。

    Args:
        db: 数据库会话。
        year: 年份。
        farm_id: 农场 ID。

    Returns:
        年度收支汇总对象，包含按类别分组统计。
    """
    records = (
        db.query(CostRecord)
        .filter(extract("year", CostRecord.record_date) == year, CostRecord.farm_id == farm_id)
        .all()
    )
    total_cost = Decimal("0")
    total_income = Decimal("0")
    by_category: dict[str, Decimal] = {}

    for r in records:
        if r.record_type == "cost":
            total_cost += r.amount
        elif r.record_type == "income":
            total_income += r.amount
        cat = f"{r.record_type}:{r.category}"
        by_category[cat] = by_category.get(cat, Decimal("0")) + r.amount

    return YearlySummary(
        year=year,
        total_cost=total_cost,
        total_income=total_income,
        net_profit=total_income - total_cost,
        by_category=by_category,
    )


async def parse_record(description: str) -> CostParseResponse:
    """使用 LLM 解析自然语言记账描述。

    Args:
        description: 用户输入的记账描述，如"买了50斤化肥花了120块"。

    Returns:
        解析后的结构化记账数据。

    Raises:
        LlmNotConfiguredError: LLM 未配置时抛出。
    """
    today = date.today().isoformat()
    prompt = (
        "请解析以下记账描述，提取记账信息。\n\n"
        "规则：\n"
        "1. record_type 只能是 'cost'（支出）或 'income'（收入）\n"
        "2. category（分类）支出可选：种子、化肥、农药、人工、水电、地租、其他\n"
        "   收入可选：销售、补贴、其他\n"
        "3. amount 是纯数字金额（不含正负号）\n"
        "4. record_date 是 YYYY-MM-DD 格式，未提及则使用今天\n"
        "5. note 是额外描述信息，没有则为空\n\n"
        "请严格返回以下 JSON 格式，不要添加任何其他内容：\n"
        '{"record_type": "...", "category": "...", "amount": "...", "record_date": "...", "note": "..."}\n\n'
        f"今天是 {today}。\n"
        f"描述：{description}"
    )

    llm = get_llm()
    messages = [{"role": "user", "content": prompt}]
    result = await llm_invoke_with_breaker(llm, messages)
    content = result.content.strip()

    # 尝试提取 JSON 内容
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()

    data = json.loads(content)
    return CostParseResponse(
        record_type=data["record_type"],
        category=data["category"],
        amount=str(data["amount"]),
        record_date=data["record_date"],
        note=data.get("note") or None,
    )


__all__ = [
    "create_record",
    "get_records",
    "get_cycle_profit",
    "get_yearly_summary",
    "parse_record",
]
