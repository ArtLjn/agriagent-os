"""种植单元（地块/棚/区域）MCP 工具。"""

from __future__ import annotations

from datetime import date

from business.db import session_scope
from business.mcp_app import mcp
from business.services import work_order_service
from business.tools._headers import require_farm_operation_permission


@mcp.tool
def manage_planting_units(
    operation: str,
    cycle_id: int | None = None,
    unit_id: int | None = None,
    name: str | None = None,
    area_mu: float | None = None,
    planted_date: str | None = None,
    status: str = "active",
    note: str | None = None,
) -> dict:
    """查询或创建真实种植单元，不使用茬口 field_name 代替。"""
    op = (operation or "").lower()
    principal = require_farm_operation_permission(
        op, read_operations={"query", "detail"}, write_operations={"create"}
    )
    farm_id = principal["farm_id"]
    with session_scope() as db:
        if op == "query":
            items = work_order_service.list_units(db, farm_id, cycle_id=cycle_id)
            return {"count": len(items), "items": items}
        if op == "create":
            if cycle_id is None:
                return {"error": "missing_cycle_id", "message": "必须提供茬口 ID"}
            if not name:
                return {"error": "missing_name", "message": "必须提供种植单元名称"}
            try:
                parsed_date = date.fromisoformat(planted_date) if planted_date else None
                return work_order_service.create_unit(
                    db,
                    farm_id=farm_id,
                    cycle_id=cycle_id,
                    name=name,
                    area_mu=area_mu,
                    planted_date=parsed_date,
                    status=status,
                    note=note,
                )
            except ValueError as exc:
                code = (
                    "invalid_planted_date"
                    if planted_date and "Invalid isoformat" in str(exc)
                    else "not_found"
                )
                return {"error": code, "message": str(exc)}
        if op == "detail":
            if unit_id is None:
                return {"error": "missing_unit_id", "message": "必须提供种植单元 ID"}
            try:
                return work_order_service.get_unit(db, unit_id, farm_id)
            except ValueError as exc:
                return {"error": "not_found", "message": str(exc)}
    return {
        "error": "invalid_operation",
        "message": "operation 必须是 query/create/detail",
    }


__all__ = ["manage_planting_units"]
