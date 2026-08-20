"""作物模板 MCP 工具。

模板创建和系统模板导入单独暴露，避免 Agent 将模板写入错误映射成茬口创建。
"""

from __future__ import annotations

from collections.abc import Mapping

from business.db import session_scope
from business.mcp_app import mcp
from business.services import crop_service
from business.tools._headers import get_farm_id_from_headers


def _error(code: str, message: str, **context: object) -> dict:
    result = {
        "error": code,
        "code": code,
        "message": message,
        "retryable": False,
    }
    if context:
        result["context"] = context
    return result


def _validate_stages(stages: object) -> tuple[list[dict] | None, dict | None]:
    """在 MCP 边界校验阶段，避免裸 KeyError 穿透到 Agent。"""
    if not isinstance(stages, list) or not stages:
        return None, _error("missing_stages", "create 操作必须提供生长阶段")

    normalized: list[dict] = []
    for index, raw_stage in enumerate(stages):
        field = f"stages[{index}]"
        if not isinstance(raw_stage, Mapping):
            return None, _error(
                "invalid_stage",
                f"{field} 必须是对象",
                field=field,
            )

        name = raw_stage.get("name")
        if not isinstance(name, str) or not name.strip():
            return None, _error(
                "invalid_stage_name",
                f"{field}.name 必须是非空字符串",
                field=f"{field}.name",
            )

        duration_days = raw_stage.get("duration_days")
        if (
            isinstance(duration_days, bool)
            or not isinstance(duration_days, int)
            or not 1 <= duration_days <= 3650
        ):
            return None, _error(
                "invalid_stage_duration",
                f"{field}.duration_days 必须是 1-3650 的整数",
                field=f"{field}.duration_days",
            )

        order_index = raw_stage.get("order_index")
        if (
            isinstance(order_index, bool)
            or not isinstance(order_index, int)
            or order_index < 0
        ):
            return None, _error(
                "invalid_stage_order",
                f"{field}.order_index 必须是非负整数",
                field=f"{field}.order_index",
            )

        key_tasks = raw_stage.get("key_tasks")
        if key_tasks is not None and (
            not isinstance(key_tasks, str) or len(key_tasks) > 500
        ):
            return None, _error(
                "invalid_stage_tasks",
                f"{field}.key_tasks 必须是不超过 500 个字符的文本",
                field=f"{field}.key_tasks",
            )

        normalized.append(
            {
                "name": name.strip(),
                "duration_days": duration_days,
                "order_index": order_index,
                "key_tasks": key_tasks,
            }
        )
    return normalized, None


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
            normalized_stages, validation_error = _validate_stages(stages)
            if validation_error is not None:
                return validation_error
            duplicate = crop_service.find_exact_duplicate(
                db,
                farm_id=farm_id,
                name=name,
                variety=variety,
                stages=normalized_stages,
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
                stages=normalized_stages,
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
