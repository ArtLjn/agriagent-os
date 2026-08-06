"""Farm log MCP tool — manage_farm_logs.

统一管理农事日志的 query/create/update/delete 四种操作，对应 agent 侧
manage_farm_logs skill。风险等级由 agent skill 根据参数动态判定：
  - operation=query  → read
  - operation=create → write_confirm
  - operation=update → write_confirm
  - operation=delete → write_high

身份注入：agent 通过 BusinessClient headers 传入 X-Farm-Id，
本工具从 HTTP 请求头读取后传给 service 层做农场隔离。
"""
from __future__ import annotations

from business.mcp_app import mcp
from business.services import log_service
from business.tools._headers import get_farm_id_from_headers


@mcp.tool
def manage_farm_logs(
    operation: str,
    cycle_id: int | None = None,
    operation_type: str | None = None,
    operation_date: str | None = None,
    note: str | None = None,
    worker_names: list[str] | None = None,
    log_id: int | None = None,
    days: int = 7,
    limit: int = 20,
) -> dict:
    """Manage farm log entries: query / create / update / delete.

    Single tool with four operations:
      - operation="query"  [RISK: read]
          查询最近农事记录，可按 cycle_id 过滤，days 限定回溯天数。
          相关参数：cycle_id (optional), days, limit。

      - operation="create" [RISK: write_confirm]
          创建一条农事记录。cycle_id 和 operation_type 必填。
          相关参数：cycle_id, operation_type, operation_date, note, worker_names。

      - operation="update" [RISK: write_confirm]
          更新一条农事记录。log_id 必填，其余参数可选（仅传需要修改的字段）。
          相关参数：log_id, cycle_id, operation_type, operation_date, note, worker_names。

      - operation="delete" [RISK: write_high]
          按 log_id 删除一条农事记录。不可恢复。
          相关参数：log_id。

    Args:
      operation: "query" | "create" | "update" | "delete"
      cycle_id: 茬口 ID（create 必填，query 可选过滤，update 可选更新）
      operation_type: 操作类型如"浇水"、"施肥"（create 必填，update 可选）
      operation_date: YYYY-MM-DD（create/update 可选，不传默认今天）
      note: 备注（create/update 可选）
      worker_names: 参与工人姓名列表（create/update 可选，update 时全量替换）
      log_id: 农事记录 ID（update/delete 必填）
      days: 查询最近 N 天（query，默认 7）
      limit: 查询返回最大条数（query，默认 20）

    Examples:
      - "最近有哪些农事" → operation="query"
      - "1号茬口最近一周农事" → operation="query", cycle_id=1, days=7
      - "今天给番茄浇水了" → operation="create", cycle_id=1, operation_type="浇水"
      - "把记录8的备注改成下午浇水" → operation="update", log_id=8, note="下午浇水"
      - "删除农事记录 8" → operation="delete", log_id=8
    """
    farm_id = get_farm_id_from_headers()
    op = (operation or "").lower()

    if op == "query":
        return log_service.query_logs(
            farm_id=farm_id, cycle_id=cycle_id, days=days, limit=limit
        )

    if op == "create":
        if not cycle_id:
            return {"error": "missing_cycle_id", "message": "create 操作必须提供 cycle_id"}
        if not operation_type:
            return {"error": "missing_operation_type",
                    "message": "create 操作必须提供 operation_type（如浇水、施肥）"}
        return log_service.create_log(
            farm_id=farm_id,
            cycle_id=cycle_id,
            operation_type=operation_type,
            operation_date=operation_date,
            note=note,
            worker_names=worker_names,
        )

    if op == "update":
        if log_id is None:
            return {"error": "missing_log_id", "message": "update 操作必须提供 log_id"}
        try:
            return log_service.update_log(
                farm_id=farm_id,
                log_id=log_id,
                cycle_id=cycle_id,
                operation_type=operation_type,
                operation_date=operation_date,
                note=note,
                worker_names=worker_names,
            )
        except ValueError as exc:
            return {"error": "not_found", "message": str(exc)}

    if op == "delete":
        if log_id is None:
            return {"error": "missing_log_id", "message": "delete 操作必须提供 log_id"}
        try:
            return log_service.delete_log(farm_id=farm_id, log_id=log_id)
        except ValueError as exc:
            return {"error": "not_found", "message": str(exc)}

    return {
        "error": "invalid_operation",
        "message": f"operation 必须是 query/create/update/delete，收到: {operation!r}",
    }
