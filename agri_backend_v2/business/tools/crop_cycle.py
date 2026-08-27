"""Crop cycle MCP tool — manage_crop_cycle.

统一管理种植茬口及作物模板的 query/detail/create/advance/update/delete/
templates/system_templates 操作。风险等级由 agent skill 根据参数动态判定：
  - operation=query / detail / templates / system_templates → read
  - operation=create / advance / update → write_confirm
  - operation=delete → write_high

身份注入：agent 通过 BusinessClient headers 传入 X-Farm-Id，
本工具从 HTTP 请求头读取后传给 service 层做农场隔离。
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from business.db import session_scope
from business.mcp_app import mcp
from business.services import crop_service, cycle_service
from business.tools._headers import require_farm_operation_permission


def _to_decimal(value, field: str) -> Decimal | None:
    """将入参转为 Decimal，None 透传；非法值抛 ValueError。"""
    if value is None:
        return None
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
def manage_crop_cycle(
    operation: str,
    cycle_id: int | None = None,
    name: str | None = None,
    crop_name: str | None = None,
    crop_template_id: int | None = None,
    start_date: str | None = None,
    field_name: str | None = None,
    total_area_mu: float | None = None,
    season: str | None = None,
    batch_note: str | None = None,
    skip: int = 0,
    limit: int = 100,
    category: str | None = None,
) -> dict:
    """Manage crop cycles and crop templates: query / detail / create / advance / update / delete / templates / system_templates.

    Single tool with eight operations:
      - operation="query"  [RISK: read]
          查询当前农场的茬口列表（分页），按 id 正序。
          相关参数：skip, limit。

      - operation="detail"  [RISK: read]
          查询单个茬口详情（含阶段信息和当前阶段名）。cycle_id 必填。
          相关参数：cycle_id。

      - operation="create" [RISK: write_confirm]
          创建一条茬口，按模板阶段顺序自动推算各阶段日期。
          必填：name, crop_template_id, start_date (YYYY-MM-DD)。
          相关参数：name, crop_template_id, start_date, field_name,
                    total_area_mu, season, batch_note。

      - operation="advance" [RISK: write_confirm]
          推进茬口到下一个生长阶段。cycle_id 必填。
          相关参数：cycle_id。

      - operation="update" [RISK: write_confirm]
          更新茬口基本信息。cycle_id、name、crop_template_id、start_date 必填。
          相关参数：cycle_id, name, crop_template_id, start_date, field_name,
                    total_area_mu, season, batch_note。

      - operation="delete" [RISK: write_high]
          删除茬口及其阶段、关联农事日志和成本记录。不可恢复。cycle_id 必填。
          相关参数：cycle_id。

      - operation="templates"  [RISK: read]
          查询当前农场的作物模板列表（分页）。
          相关参数：skip, limit。

      - operation="system_templates"  [RISK: read]
          查询系统预设作物模板，可按分类筛选。
          相关参数：category。

    Args:
      operation: "query" | "detail" | "create" | "advance" | "update" |
                 "delete" | "templates" | "system_templates"
      cycle_id: 茬口 ID（detail/advance/update/delete 必填）
      name: 茬口名称（create/update 必填）
      crop_name: 目标作物名称（Agent 创建茬口时必填，用于模板一致性校验）
      crop_template_id: 作物模板 ID（create/update 必填）
      start_date: 起始日期 YYYY-MM-DD（create/update 必填）
      field_name: 地块名称
      total_area_mu: 总面积（亩）
      season: 季节
      batch_note: 批次备注
      skip: 分页跳过条数（query/templates，默认 0）
      limit: 分页返回最大条数（query/templates，默认 100）
      category: 作物分类（system_templates 可选筛选）

    Examples:
      - "有哪些茬口" → operation="query"
      - "茬口 3 的详情" → operation="detail", cycle_id=3
      - "创建番茄茬口" → operation="create", name="番茄-春季",
        crop_template_id=1, start_date="2026-03-01"
      - "推进茬口 3 到下一阶段" → operation="advance", cycle_id=3
      - "有哪些作物模板" → operation="templates"
      - "系统有哪些作物模板" → operation="system_templates"
    """
    op = (operation or "").lower()
    farm_id = require_farm_operation_permission(
        op,
        tool_name="manage_crop_cycle",
    )["farm_id"]

    if op == "query":
        with session_scope() as db:
            cycles = cycle_service.get_crop_cycles(db, farm_id, skip=skip, limit=limit)
            return {"count": len(cycles), "cycles": cycles}

    if op == "detail":
        if cycle_id is None:
            return {
                "error": "missing_cycle_id",
                "message": "detail 操作必须提供 cycle_id",
            }
        with session_scope() as db:
            cycle = cycle_service.get_crop_cycle(db, cycle_id, farm_id)
            if cycle is None:
                return {"error": "not_found", "message": f"茬口 {cycle_id} 不存在"}
            return cycle

    if op == "create":
        if not name:
            return {"error": "missing_name", "message": "create 操作必须提供 name"}
        if not crop_name:
            return {
                "error": "missing_crop_name",
                "message": "create 操作必须提供 crop_name",
            }
        if crop_template_id is None:
            return {
                "error": "missing_crop_template_id",
                "message": "create 操作必须提供 crop_template_id",
            }
        if not start_date:
            return {
                "error": "missing_start_date",
                "message": "create 操作必须提供 start_date (YYYY-MM-DD)",
            }
        try:
            parsed_start = _to_date(start_date, "start_date")
            area = _to_decimal(total_area_mu, "total_area_mu")
        except ValueError as exc:
            return {"error": "invalid_param", "message": str(exc)}
        try:
            with session_scope() as db:
                return cycle_service.create_crop_cycle(
                    db,
                    farm_id=farm_id,
                    name=name,
                    crop_template_id=crop_template_id,
                    start_date=parsed_start,
                    field_name=field_name,
                    total_area_mu=area,
                    season=season,
                    batch_note=batch_note,
                    expected_crop_name=crop_name,
                )
        except ValueError as exc:
            message = str(exc)
            if message.startswith("crop_template_mismatch:"):
                code = "crop_template_mismatch"
            elif message.startswith("system_template_not_imported:"):
                code = "system_template_not_imported"
            else:
                code = "not_found"
            return {"error": code, "message": message}

    if op == "advance":
        if cycle_id is None:
            return {
                "error": "missing_cycle_id",
                "message": "advance 操作必须提供 cycle_id",
            }
        try:
            with session_scope() as db:
                return cycle_service.advance_stage(db, cycle_id, farm_id)
        except ValueError as exc:
            return {"error": "not_found", "message": str(exc)}

    if op == "update":
        if cycle_id is None:
            return {
                "error": "missing_cycle_id",
                "message": "update 操作必须提供 cycle_id",
            }
        if not name:
            return {"error": "missing_name", "message": "update 操作必须提供 name"}
        if crop_template_id is None:
            return {
                "error": "missing_crop_template_id",
                "message": "update 操作必须提供 crop_template_id",
            }
        if not start_date:
            return {
                "error": "missing_start_date",
                "message": "update 操作必须提供 start_date (YYYY-MM-DD)",
            }
        try:
            parsed_start = _to_date(start_date, "start_date")
            area = _to_decimal(total_area_mu, "total_area_mu")
        except ValueError as exc:
            return {"error": "invalid_param", "message": str(exc)}
        try:
            with session_scope() as db:
                return cycle_service.update_crop_cycle(
                    db,
                    cycle_id,
                    farm_id=farm_id,
                    name=name,
                    crop_template_id=crop_template_id,
                    start_date=parsed_start,
                    field_name=field_name,
                    total_area_mu=area,
                    season=season,
                    batch_note=batch_note,
                )
        except ValueError as exc:
            return {"error": "not_found", "message": str(exc)}

    if op == "delete":
        if cycle_id is None:
            return {
                "error": "missing_cycle_id",
                "message": "delete 操作必须提供 cycle_id",
            }
        try:
            with session_scope() as db:
                cycle_service.delete_crop_cycle(db, cycle_id, farm_id)
            return {"deleted": cycle_id}
        except ValueError as exc:
            return {"error": "not_found", "message": str(exc)}

    if op == "templates":
        with session_scope() as db:
            templates = crop_service.get_crop_templates(
                db, farm_id, skip=skip, limit=limit
            )
            return {"count": len(templates), "templates": templates}

    if op == "system_templates":
        with session_scope() as db:
            templates = crop_service.list_system_templates(db, category)
            return {"count": len(templates), "templates": templates}

    return {
        "error": "invalid_operation",
        "message": (
            "operation 必须是 query/detail/create/advance/update/delete/"
            f"templates/system_templates，收到: {operation!r}"
        ),
    }
