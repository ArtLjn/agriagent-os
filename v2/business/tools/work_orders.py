"""Work order MCP tool — manage_work_orders.

统一管理农事作业单的 query/detail/create/update/settle 操作。风险等级由
agent skill 根据参数动态判定：
  - operation=query / detail → read
  - operation=create / update / settle → write_confirm

身份注入：agent 通过 BusinessClient headers 传入 X-Farm-Id，
本工具从 HTTP 请求头读取后传给 service 层做农场隔离。

update 操作使用 _UNSET 哨兵区分"未提供该字段"（保持原值）和"显式传值"：
MCP 入参为 None 表示未提供 → 转为 _UNSET 透传给 service 层。
"""
from __future__ import annotations

from datetime import date

from business.db import session_scope
from business.mcp_app import mcp
from business.services import work_order_service
from business.services.work_order_service import _UNSET
from business.tools._headers import get_farm_id_from_headers


def _to_date(value: str | None, field: str) -> date | None:
    """将 YYYY-MM-DD 字符串转为 date，None 透传；非法值抛 ValueError。"""
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{field} 格式应为 YYYY-MM-DD，收到: {value!r}")


@mcp.tool
def manage_work_orders(
    operation: str,
    work_order_id: int | None = None,
    operation_type: str | None = None,
    operation_date: str | None = None,
    cycle_id: int | None = None,
    scope_type: str | None = None,
    note: str | None = None,
    amount: float | None = None,
    worker_name: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> dict:
    """Manage farm work orders: query / detail / create / update / settle.

    Single tool with five operations:
      - operation="query"  [RISK: read]
          查询作业单列表（分页），可按 cycle_id 过滤，按作业日期倒序。
          相关参数：cycle_id, skip, limit。

      - operation="detail"  [RISK: read]
          查询单个作业单详情（含用工明细和种植单元）。work_order_id 必填。
          相关参数：work_order_id。

      - operation="create" [RISK: write_confirm]
          创建作业单。必填：operation_type、operation_date (YYYY-MM-DD)。
          相关参数：operation_type, operation_date, cycle_id, scope_type, note。

      - operation="update" [RISK: write_confirm]
          更新作业单，只更新传入的字段（未传字段保持原值）。work_order_id 必填。
          相关参数：work_order_id, operation_type, operation_date, cycle_id,
                    scope_type, note。

      - operation="settle" [RISK: write_confirm]
          按筛选条件结算未付人工。amount 不传则全额结算。
          相关参数：amount, worker_name, cycle_id, work_order_id,
                    start_date, end_date。

    Args:
      operation: "query" | "detail" | "create" | "update" | "settle"
      work_order_id: 作业单 ID（detail/update 必填，settle 可选筛选）
      operation_type: 作业类型如"浇水"、"施肥"（create 必填，update 可选）
      operation_date: 作业日期 YYYY-MM-DD（create 必填，update 可选）
      cycle_id: 茬口 ID（create 可选关联，query 可选过滤，settle 可选筛选）
      scope_type: 作业范围 cycle / unit / farm（create 默认 cycle，update 可选）
      note: 备注（create/update 可选）
      amount: 结算金额（settle 可选，不传则全额结算）
      worker_name: 工人姓名（settle 可选筛选）
      start_date: 起始日期 YYYY-MM-DD（settle 可选筛选）
      end_date: 结束日期 YYYY-MM-DD（settle 可选筛选）
      skip: 分页跳过条数（query，默认 0）
      limit: 分页返回最大条数（query，默认 100）

    Examples:
      - "最近有哪些作业单" → operation="query"
      - "茬口 3 的作业单" → operation="query", cycle_id=3
      - "作业单 5 的详情" → operation="detail", work_order_id=5
      - "创建一条浇水作业单" → operation="create",
        operation_type="浇水", operation_date="2026-03-01", cycle_id=3
      - "把作业单 5 的备注改成下午浇水" → operation="update",
        work_order_id=5, note="下午浇水"
      - "结算张三的未付人工 200 元" → operation="settle",
        worker_name="张三", amount=200
    """
    farm_id = get_farm_id_from_headers()
    op = (operation or "").lower()

    if op == "query":
        with session_scope() as db:
            work_orders = work_order_service.list_work_orders(
                db, farm_id, cycle_id=cycle_id, skip=skip, limit=limit
            )
            return {"count": len(work_orders), "work_orders": work_orders}

    if op == "detail":
        if work_order_id is None:
            return {
                "error": "missing_work_order_id",
                "message": "detail 操作必须提供 work_order_id",
            }
        with session_scope() as db:
            wo = work_order_service.get_work_order(db, work_order_id, farm_id)
            if wo is None:
                return {
                    "error": "not_found",
                    "message": f"作业单 {work_order_id} 不存在",
                }
            return wo

    if op == "create":
        if not operation_type:
            return {
                "error": "missing_operation_type",
                "message": "create 操作必须提供 operation_type",
            }
        if not operation_date:
            return {
                "error": "missing_operation_date",
                "message": "create 操作必须提供 operation_date (YYYY-MM-DD)",
            }
        try:
            parsed_date = _to_date(operation_date, "operation_date")
        except ValueError as exc:
            return {"error": "invalid_param", "message": str(exc)}
        try:
            with session_scope() as db:
                return work_order_service.create_work_order(
                    db,
                    farm_id=farm_id,
                    operation_type=operation_type,
                    operation_date=parsed_date,
                    cycle_id=cycle_id,
                    scope_type=scope_type or "cycle",
                    note=note,
                )
        except ValueError as exc:
            return {"error": "invalid_param", "message": str(exc)}

    if op == "update":
        if work_order_id is None:
            return {
                "error": "missing_work_order_id",
                "message": "update 操作必须提供 work_order_id",
            }
        try:
            parsed_op_date = (
                _to_date(operation_date, "operation_date")
                if operation_date is not None
                else _UNSET
            )
        except ValueError as exc:
            return {"error": "invalid_param", "message": str(exc)}
        try:
            with session_scope() as db:
                return work_order_service.update_work_order(
                    db,
                    work_order_id,
                    farm_id=farm_id,
                    cycle_id=_UNSET if cycle_id is None else cycle_id,
                    operation_type=(
                        _UNSET if operation_type is None else operation_type
                    ),
                    operation_date=parsed_op_date,
                    scope_type=_UNSET if scope_type is None else scope_type,
                    note=_UNSET if note is None else note,
                )
        except ValueError as exc:
            return {"error": "invalid_param", "message": str(exc)}

    if op == "settle":
        try:
            parsed_start = (
                _to_date(start_date, "start_date") if start_date is not None else None
            )
            parsed_end = _to_date(end_date, "end_date") if end_date is not None else None
        except ValueError as exc:
            return {"error": "invalid_param", "message": str(exc)}
        try:
            with session_scope() as db:
                return work_order_service.settle_labor_payment(
                    db,
                    farm_id,
                    amount=amount,
                    worker_name=worker_name,
                    cycle_id=cycle_id,
                    work_order_id=work_order_id,
                    start_date=parsed_start,
                    end_date=parsed_end,
                )
        except ValueError as exc:
            return {"error": "not_found", "message": str(exc)}

    return {
        "error": "invalid_operation",
        "message": f"operation 必须是 query/detail/create/update/settle，收到: {operation!r}",
    }
