import json
import logging
from decimal import Decimal
from datetime import date

from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.schemas.cost import CostRecordCreate, CycleProfit, YearlySummary, CostParseResponse, CostRecordUpdate
from app.core.llm import get_llm, llm_invoke_with_breaker

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


def get_records_filtered(
    db: Session,
    farm_id: int,
    cycle_id: int | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[CostRecord]:
    """查询成本记账记录列表（支持日期范围筛选）。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID。
        cycle_id: 按种植周期 ID 筛选（可选）。
        category: 按类别筛选（可选）。
        date_from: 起始日期（可选）。
        date_to: 结束日期（可选）。

    Returns:
        符合条件的 CostRecord 列表，按记录日期倒序排列。
    """
    query = db.query(CostRecord).filter(CostRecord.farm_id == farm_id)
    if cycle_id is not None:
        query = query.filter(CostRecord.cycle_id == cycle_id)
    if category is not None:
        query = query.filter(CostRecord.category == category)
    if date_from is not None:
        query = query.filter(CostRecord.record_date >= date_from)
    if date_to is not None:
        query = query.filter(CostRecord.record_date <= date_to)
    return query.order_by(CostRecord.record_date.desc()).all()


def get_record_by_id(db: Session, record_id: int, farm_id: int) -> CostRecord | None:
    """根据 ID 查询单条成本记账记录。

    Args:
        db: 数据库会话。
        record_id: 记录 ID。
        farm_id: 农场 ID。

    Returns:
        CostRecord 实例，不存在时返回 None。
    """
    return (
        db.query(CostRecord)
        .filter(CostRecord.id == record_id, CostRecord.farm_id == farm_id)
        .first()
    )


def update_record(
    db: Session, record_id: int, update: CostRecordUpdate, farm_id: int
) -> CostRecord:
    """更新一条成本或收入记录。

    Args:
        db: 数据库会话。
        record_id: 记录 ID。
        update: 更新请求数据。
        farm_id: 农场 ID。

    Returns:
        更新后的 CostRecord 实例。

    Raises:
        ValueError: 记录不存在时抛出。
    """
    db_record = get_record_by_id(db, record_id, farm_id)
    if not db_record:
        raise ValueError(f"记录 {record_id} 不存在")

    update_data = update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_record, field, value)

    db.commit()
    db.refresh(db_record)
    return db_record


def delete_record(db: Session, record_id: int, farm_id: int) -> None:
    """删除一条成本或收入记录。

    Args:
        db: 数据库会话。
        record_id: 记录 ID。
        farm_id: 农场 ID。

    Raises:
        ValueError: 记录不存在时抛出。
    """
    db_record = get_record_by_id(db, record_id, farm_id)
    if not db_record:
        raise ValueError(f"记录 {record_id} 不存在")

    db.delete(db_record)
    db.commit()


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


async def parse_record(description: str, farm_id: int | None = None, db: Session | None = None) -> CostParseResponse:
    """使用 LLM 解析自然语言记账描述。

    Args:
        description: 用户输入的记账描述，如"买了50斤化肥花了120块"。
        farm_id: 农场 ID（可选，用于动态获取自定义分类）。
        db: 数据库会话（可选，farm_id 提供时必须提供）。

    Returns:
        解析后的结构化记账数据。

    Raises:
        LlmNotConfiguredError: LLM 未配置时抛出。
    """
    today = date.today().isoformat()

    # 构建分类提示
    cost_categories = "种子、化肥、农药、人工、水电、地租、其他"
    income_categories = "销售、补贴、其他"

    # 如果提供了 farm_id 和 db，动态获取自定义分类
    if farm_id is not None and db is not None:
        from app.services.cost_category_service import get_categories

        categories = get_categories(db, farm_id)
        if categories:
            # 按类型分组
            cost_cats = [c.name for c in categories if c.type == "cost"]
            income_cats = [c.name for c in categories if c.type == "income"]
            if cost_cats:
                cost_categories = "、".join(cost_cats)
            if income_cats:
                income_categories = "、".join(income_cats)

    prompt = (
        "请解析以下记账描述，提取记账信息。\n\n"
        "规则：\n"
        "1. record_type 只能是 'cost'（支出）或 'income'（收入）\n"
        f"2. category（分类）支出可选：{cost_categories}\n"
        f"   收入可选：{income_categories}\n"
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
    "get_records_filtered",
    "get_record_by_id",
    "update_record",
    "delete_record",
    "get_cycle_profit",
    "get_yearly_summary",
    "parse_record",
]
