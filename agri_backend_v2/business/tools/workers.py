"""Worker profile MCP tool — manage_workers.

统一管理工人档案的 query/create/update/delete 操作。风险等级由 agent skill
根据参数动态判定：
  - operation=query → read
  - operation=create / update → write_confirm
  - operation=delete → write_confirm（软停用，保留历史用工，非破坏性）

身份注入：agent 通过 BusinessClient headers 传入 X-Farm-Id，
本工具从 HTTP 请求头读取后传给 service 层做农场隔离。
"""

from __future__ import annotations

from business.db import session_scope
from business.mcp_app import mcp
from business.services import worker_service
from business.tools._headers import require_farm_operation_permission


@mcp.tool
def manage_workers(
    operation: str,
    worker_id: int | None = None,
    name: str | None = None,
    phone: str | None = None,
    default_pay_type: str | None = None,
    default_unit_price: float | None = None,
    note: str | None = None,
    status: str | None = None,
    active_only: bool = False,
) -> dict:
    """Manage worker profiles: query / create / update / delete.

    Single tool with four operations:
      - operation="query"  [RISK: read]
          查询工人档案列表，可只看在职工人。
          相关参数：active_only。

      - operation="create" [RISK: write_confirm]
          创建工人档案；同名允许，电话在当前农场内必须唯一。name 必填。
          同名且未提供电话时，如果已有同名档案则返回歧义，不会覆盖已有档案。
          相关参数：name, phone, default_pay_type, default_unit_price, note。

      - operation="update" [RISK: write_confirm]
          更新工人档案，只更新传入的字段。worker_id 必填。
          相关参数：worker_id, name, phone, default_pay_type,
                    default_unit_price, note, status。

      - operation="delete" [RISK: write_confirm]
          停用工人档案（保留历史用工，不物理删除）。worker_id 必填。
          相关参数：worker_id。

    Args:
      operation: "query" | "create" | "update" | "delete"
      worker_id: 工人 ID（update/delete 必填）
      name: 工人姓名（create 必填，update 可选）
      phone: 联系电话
      default_pay_type: 默认计酬方式，如 daily / piece（create 默认 daily）
      default_unit_price: 默认单价
      note: 备注
      status: 状态（update 可选，如 active / inactive）
      active_only: query 时是否只看在职工人（默认 False）

    Examples:
      - "有哪些工人" → operation="query"
      - "在职工人有哪些" → operation="query", active_only=True
      - "添加工人张三" → operation="create", name="张三"
      - "把工人 5 的电话改成 13800000000" → operation="update",
        worker_id=5, phone="13800000000"
      - "停用工人 5" → operation="delete", worker_id=5
    """
    op = (operation or "").lower()
    farm_id = require_farm_operation_permission(
        op,
        tool_name="manage_workers",
    )["farm_id"]

    if op == "query":
        with session_scope() as db:
            workers = worker_service.list_workers(db, farm_id, active_only=active_only)
            return {"count": len(workers), "workers": workers}

    if op == "create":
        if not name:
            return {"error": "missing_name", "message": "create 操作必须提供 name"}
        with session_scope() as db:
            try:
                return worker_service.create_worker(
                    db,
                    farm_id=farm_id,
                    name=name,
                    phone=phone,
                    default_pay_type=default_pay_type or "daily",
                    default_unit_price=default_unit_price,
                    note=note,
                )
            except worker_service.WorkerIdentityError as exc:
                return {
                    "code": exc.code,
                    "error": exc.code,
                    "message": str(exc),
                    "meta": exc.meta,
                }

    if op == "update":
        if worker_id is None:
            return {
                "error": "missing_worker_id",
                "message": "update 操作必须提供 worker_id",
            }
        try:
            with session_scope() as db:
                return worker_service.update_worker(
                    db,
                    worker_id,
                    farm_id=farm_id,
                    name=name,
                    phone=phone,
                    default_pay_type=default_pay_type,
                    default_unit_price=default_unit_price,
                    note=note,
                    status=status,
                )
        except worker_service.WorkerIdentityError as exc:
            return {
                "code": exc.code,
                "error": exc.code,
                "message": str(exc),
                "meta": exc.meta,
            }
        except ValueError as exc:
            return {"error": "not_found", "message": str(exc)}

    if op == "delete":
        if worker_id is None:
            return {
                "error": "missing_worker_id",
                "message": "delete 操作必须提供 worker_id",
            }
        try:
            with session_scope() as db:
                return worker_service.delete_worker(db, worker_id, farm_id)
        except ValueError as exc:
            return {"error": "not_found", "message": str(exc)}

    return {
        "error": "invalid_operation",
        "message": f"operation 必须是 query/create/update/delete，收到: {operation!r}",
    }
