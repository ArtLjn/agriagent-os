"""Debt (赊账) management MCP tool — manage_debt.

统一管理赊账记录的 query/create/repay/summary 操作。风险等级由 agent skill
根据参数动态判定：
  - operation=query / summary → read
  - operation=create / repay → write_confirm

身份注入：agent 通过 BusinessClient headers 传入 X-Farm-Id，
本工具从 HTTP 请求头读取后传给 service 层做农场隔离。

record_type 映射：debt_payable（应付，我欠他人）→ cost；
debt_receivable（应收，他人欠我）→ income。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from business.db import session_scope
from business.mcp_app import mcp
from business.services import debt_service
from business.tools._headers import require_farm_operation_permission

# 赊账方向映射：agent 传入语义化的 payable/receivable，service 层用 cost/income。
_DEBT_TYPE_MAP = {
    "debt_payable": "cost",
    "debt_receivable": "income",
}


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


@mcp.tool
def manage_debt(
    operation: str,
    record_type: str | None = None,
    category: str | None = None,
    amount: float | None = None,
    record_date: str | None = None,
    cycle_id: int | None = None,
    note: str | None = None,
    counterparty: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> dict:
    """Manage debt (赊账) records: query / create / repay / summary.

    Single tool with four operations:
      - operation="query"  [RISK: read]
          查询未结清的赊账记录列表（分页），可按交易对手模糊筛选。
          相关参数：counterparty, skip, limit。

      - operation="create" [RISK: write_confirm]
          创建一条赊账记录。必填：record_type (debt_payable/debt_receivable)、
          amount、record_date (YYYY-MM-DD)。category 默认"赊账"。
          相关参数：record_type, category, amount, record_date, cycle_id,
                    note, counterparty。

      - operation="repay" [RISK: write_confirm]
          结清指定交易对手最早的未结清赊账记录。counterparty 必填。
          amount 不传则全额还清，传值则部分结算。
          相关参数：counterparty, amount, note。

      - operation="summary"  [RISK: read]
          按交易对手分组统计未结清债务情况。
          相关参数：无。

    Args:
      operation: "query" | "create" | "repay" | "summary"
      record_type: 赊账方向 debt_payable（应付）或 debt_receivable（应收）（create 必填）
      category: 分类名（create 可选，默认"赊账"）
      amount: 金额（create 必填；repay 可选，不传则全额还清）
      record_date: 记录日期 YYYY-MM-DD（create 必填）
      cycle_id: 茬口 ID（create 可选关联）
      note: 备注（create/repay 可选）
      counterparty: 交易对手（query 可选模糊筛选；repay 必填精确匹配）
      skip: 分页跳过条数（query，默认 0）
      limit: 分页返回最大条数（query，默认 100）

    Examples:
      - "有哪些未结清的赊账" → operation="query"
      - "张三的赊账记录" → operation="query", counterparty="张三"
      - "记一笔赊账：向农资店赊化肥 300 元" → operation="create",
        record_type="debt_payable", amount=300, record_date="2026-03-01",
        counterparty="农资店"
      - "还张三 200 元" → operation="repay", counterparty="张三", amount=200
      - "还清张三全部赊账" → operation="repay", counterparty="张三"
      - "赊账汇总" → operation="summary"
    """
    op = (operation or "").lower()
    farm_id = require_farm_operation_permission(
        op,
        tool_name="manage_debt",
    )["farm_id"]

    if op == "query":
        with session_scope() as db:
            debts = debt_service.get_debt_records(
                db,
                farm_id=farm_id,
                counterparty=counterparty,
                skip=skip,
                limit=limit,
            )
            return {"count": len(debts), "debts": debts}

    if op == "create":
        if not record_type:
            return {
                "error": "missing_record_type",
                "message": "create 操作必须提供 record_type (debt_payable/debt_receivable)",
            }
        mapped_type = _DEBT_TYPE_MAP.get(record_type)
        if mapped_type is None:
            return {
                "error": "invalid_record_type",
                "message": (
                    f"record_type 必须是 debt_payable 或 debt_receivable，"
                    f"收到: {record_type!r}"
                ),
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
            return debt_service.create_debt_record(
                db,
                farm_id=farm_id,
                record_type=mapped_type,
                category=category or "赊账",
                amount=parsed_amount,
                record_date=parsed_date,
                cycle_id=cycle_id,
                note=note,
                counterparty=counterparty,
            )

    if op == "repay":
        if not counterparty:
            return {
                "error": "missing_counterparty",
                "message": "repay 操作必须提供 counterparty",
            }
        if amount is None:
            parsed_amount = None
        else:
            try:
                parsed_amount = _to_decimal(amount, "amount")
            except ValueError as exc:
                return {"error": "invalid_param", "message": str(exc)}
        try:
            with session_scope() as db:
                return debt_service.settle_debt(
                    db,
                    farm_id=farm_id,
                    counterparty=counterparty,
                    amount=parsed_amount,
                    note=note,
                )
        except debt_service.InvalidSettlementAmountError as exc:
            return {"error": "invalid_param", "message": str(exc)}
        except ValueError as exc:
            return {"error": "not_found", "message": str(exc)}

    if op == "summary":
        with session_scope() as db:
            summaries = debt_service.get_debt_summary(db, farm_id=farm_id)
            return {"summaries": summaries}

    return {
        "error": "invalid_operation",
        "message": f"operation 必须是 query/create/repay/summary，收到: {operation!r}",
    }
