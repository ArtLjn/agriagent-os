"""Cost accounting MCP tool — manage_cost.

统一管理成本记账的 query/create/summary/profit/delete/categories 操作。
风险等级由 agent skill 根据参数动态判定：
  - operation=query / summary / profit / categories → read
  - operation=create → write_confirm
  - operation=delete → write_high

身份注入：agent 通过 BusinessClient headers 传入 X-Farm-Id，
本工具从 HTTP 请求头读取后传给 service 层做农场隔离。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from business.db import session_scope
from business.mcp_app import mcp
from business.services import cost_category_service, cost_service
from business.tools._headers import get_farm_id_from_headers


def _to_decimal(value, field: str) -> Decimal:
    """将入参转为 Decimal；非法值抛 ValueError。"""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} 必须是有效数字，收到: {value!r}")


def _to_date(value: str, field: str) -> date:
    """将 YYYY-MM-DD 字符串转为 date；非法值抛 ValueError。"""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field} 格式应为 YYYY-MM-DD，收到: {value!r}")


def _category_to_dict(category) -> dict:
    """ORM CostCategory → dict。"""
    return {
        "id": category.id,
        "farm_id": category.farm_id,
        "name": category.name,
        "type": category.type,
        "icon": category.icon,
        "sort_order": category.sort_order,
        "is_default": bool(category.is_default),
    }


@mcp.tool
def manage_cost(
    operation: str,
    record_type: str | None = None,
    category: str | None = None,
    amount: float | None = None,
    record_date: str | None = None,
    cycle_id: int | None = None,
    note: str | None = None,
    counterparty: str | None = None,
    record_id: int | None = None,
    year: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> dict:
    """Manage cost & income records: query / create / summary / profit / delete / categories.

    Single tool with six operations:
      - operation="query"  [RISK: read]
          查询成本/收入记录列表（分页），可按 cycle_id 和 category 过滤。
          相关参数：cycle_id, category, skip, limit。

      - operation="create" [RISK: write_confirm]
          创建一条成本或收入记录。必填：record_type (cost/income)、category、
          amount、record_date (YYYY-MM-DD)。
          相关参数：record_type, category, amount, record_date, cycle_id,
                    note, counterparty。

      - operation="summary"  [RISK: read]
          查询指定年度的收支汇总（含按类别分组）。year 必填。
          相关参数：year。

      - operation="profit"  [RISK: read]
          查询指定茬口的利润（含已结清/未结清金额）。cycle_id 必填。
          相关参数：cycle_id。

      - operation="delete" [RISK: write_high]
          软删除一条成本/收入记录。record_id 必填。
          相关参数：record_id。

      - operation="categories"  [RISK: read]
          查询当前农场的成本/收入分类列表。
          相关参数：无。

    Args:
      operation: "query" | "create" | "summary" | "profit" | "delete" | "categories"
      record_type: 记录类型 cost 或 income（create 必填）
      category: 分类名，如"种子"、"化肥"（create 必填，query 可选过滤）
      amount: 金额（create 必填）
      record_date: 记录日期 YYYY-MM-DD（create 必填）
      cycle_id: 茬口 ID（create 可选关联，query/profit 用于过滤或计算）
      note: 备注（create 可选）
      counterparty: 交易对手（create 可选）
      record_id: 记录 ID（delete 必填）
      year: 年份，如 2026（summary 必填）
      skip: 分页跳过条数（query，默认 0）
      limit: 分页返回最大条数（query，默认 100）

    Examples:
      - "最近有哪些支出" → operation="query"
      - "茬口 3 的成本记录" → operation="query", cycle_id=3
      - "记一笔化肥支出 200 元" → operation="create", record_type="cost",
        category="化肥", amount=200, record_date="2026-03-01"
      - "2026 年收支汇总" → operation="summary", year=2026
      - "茬口 3 利润多少" → operation="profit", cycle_id=3
      - "删除记录 8" → operation="delete", record_id=8
      - "有哪些成本分类" → operation="categories"
    """
    farm_id = get_farm_id_from_headers()
    op = (operation or "").lower()

    if op == "query":
        with session_scope() as db:
            records = cost_service.get_records(
                db,
                farm_id=farm_id,
                cycle_id=cycle_id,
                category=category,
                skip=skip,
                limit=limit,
            )
            return {"count": len(records), "records": records}

    if op == "create":
        if not record_type:
            return {
                "error": "missing_record_type",
                "message": "create 操作必须提供 record_type (cost/income)",
            }
        if record_type not in ("cost", "income"):
            return {
                "error": "invalid_record_type",
                "message": f"record_type 必须是 cost 或 income，收到: {record_type!r}",
            }
        if not category:
            return {
                "error": "missing_category",
                "message": "create 操作必须提供 category",
            }
        if amount is None:
            return {
                "error": "missing_amount",
                "message": "create 操作必须提供 amount",
            }
        if not record_date:
            return {
                "error": "missing_record_date",
                "message": "create 操作必须提供 record_date (YYYY-MM-DD)",
            }
        try:
            parsed_amount = _to_decimal(amount, "amount")
            parsed_date = _to_date(record_date, "record_date")
        except ValueError as exc:
            return {"error": "invalid_param", "message": str(exc)}
        with session_scope() as db:
            return cost_service.create_record(
                db,
                farm_id=farm_id,
                record_type=record_type,
                category=category,
                amount=parsed_amount,
                record_date=parsed_date,
                cycle_id=cycle_id,
                note=note,
                counterparty=counterparty,
            )

    if op == "summary":
        if year is None:
            return {
                "error": "missing_year",
                "message": "summary 操作必须提供 year",
            }
        with session_scope() as db:
            return cost_service.get_yearly_summary(db, farm_id=farm_id, year=year)

    if op == "profit":
        if cycle_id is None:
            return {
                "error": "missing_cycle_id",
                "message": "profit 操作必须提供 cycle_id",
            }
        with session_scope() as db:
            return cost_service.get_cycle_profit(db, farm_id=farm_id, cycle_id=cycle_id)

    if op == "delete":
        if record_id is None:
            return {
                "error": "missing_record_id",
                "message": "delete 操作必须提供 record_id",
            }
        with session_scope() as db:
            result = cost_service.delete_record(
                db, farm_id=farm_id, record_id=record_id
            )
            if result is None:
                return {"error": "not_found", "message": f"记录 {record_id} 不存在"}
            return result

    if op == "categories":
        with session_scope() as db:
            cats = cost_category_service.get_categories(db, farm_id)
            serialized = [_category_to_dict(c) for c in cats]
            return {"count": len(serialized), "categories": serialized}

    return {
        "error": "invalid_operation",
        "message": (
            f"operation 必须是 query/create/summary/profit/delete/categories，"
            f"收到: {operation!r}"
        ),
    }
