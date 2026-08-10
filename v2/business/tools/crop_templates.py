"""作物模板 MCP 工具。

模板创建和系统模板导入单独暴露，避免 Agent 将模板写入错误映射成茬口创建。
"""

from __future__ import annotations

from business.db import session_scope
from business.mcp_app import mcp
from business.services import crop_service
from business.tools._headers import get_farm_id_from_headers


def _error(code: str, message: str) -> dict:
    return {"error": code, "message": message}


@mcp.tool
def manage_crop_templates(
    operation: str,
    name: str | None = None,
    variety: str | None = None,
    category: str | None = None,
    stages: list[dict] | None = None,
    template_id: int | None = None,
    system_template_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
) -> dict:
    """查询、创建农场模板，或导入系统模板。"""
    farm_id = get_farm_id_from_headers()
    op = (operation or "").lower()
    with session_scope() as db:
        if op == "query":
            templates = crop_service.get_crop_templates(db, farm_id, skip, limit)
            return {"count": len(templates), "templates": templates}
        if op == "create":
            if not name:
                return _error("missing_name", "create 操作必须提供模板名称")
            if not stages:
                return _error("missing_stages", "create 操作必须提供生长阶段")
            duplicate = crop_service.find_exact_duplicate(
                db,
                farm_id=farm_id,
                name=name,
                variety=variety,
                stages=stages,
            )
            if duplicate is not None:
                existing = crop_service.get_crop_template(db, duplicate.id, farm_id)
                return {**existing, "already_exists": True}
            created = crop_service.create_crop_template(
                db,
                farm_id=farm_id,
                name=name,
                variety=variety,
                category=category,
                stages=stages,
            )
            return {**created, "already_exists": False}
        if op == "import_system":
            if system_template_id is None:
                return _error(
                    "missing_system_template_id",
                    "import_system 操作必须提供系统模板 ID",
                )
            try:
                result = crop_service.import_system_template(
                    db, system_template_id, farm_id
                )
            except ValueError as exc:
                return _error("system_template_not_found", str(exc))
            return {
                "id": result.template_id,
                "already_exists": result.already_exists,
            }
        if op == "detail":
            if template_id is None:
                return _error("missing_template_id", "detail 操作必须提供模板 ID")
            template = crop_service.get_crop_template(db, template_id, farm_id)
            return template or _error("not_found", "模板不存在")
    return _error(
        "invalid_operation", "operation 必须是 query/create/import_system/detail"
    )


__all__ = ["manage_crop_templates"]
