"""完整种植计划 MCP 工具。

Agent 先准备只读计划，再一次确认提交；Business 负责跨模板、茬口、种植单元的
事务和幂等，避免 LLM 自己编排数据库 CRUD。
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from business.db import session_scope
from business.mcp_app import mcp
from business.services import planting_plan_service
from business.tools._headers import require_farm_operation_permission


def _handle_error(
    exc: planting_plan_service.PlantingPlanError,
    *,
    status: str = "failed",
) -> dict:
    return {
        "status": status,
        "error": exc.code,
        "code": exc.code,
        "message": exc.message,
        **exc.context,
    }


@mcp.tool
def prepare_planting_plan(
    crop_name: str,
    total_area_mu: float | None = None,
    field_name: str | None = None,
    field_location: str | None = None,
    field_location_confirmed: bool = False,
    start_date: str | None = None,
    cycle_name: str | None = None,
    variety: str | None = None,
    template_strategy: str = "auto",
    template_id: int | None = None,
    system_template_id: int | None = None,
    custom_template: dict | None = None,
    advisory: dict | None = None,
) -> dict:
    """准备种植计划，不创建业务实体。"""
    try:
        farm_id = require_farm_operation_permission(
            "prepare", tool_name="prepare_planting_plan"
        )["farm_id"]
        with session_scope() as db:
            return planting_plan_service.prepare_planting_plan(
                db,
                farm_id=farm_id,
                crop_name=crop_name,
                total_area_mu=total_area_mu,
                field_name=field_name,
                field_location=field_location,
                field_location_confirmed=field_location_confirmed,
                start_date=start_date,
                cycle_name=cycle_name,
                variety=variety,
                template_strategy=template_strategy,
                template_id=template_id,
                system_template_id=system_template_id,
                custom_template=custom_template,
                advisory=advisory,
            )
    except planting_plan_service.PlantingPlanError as exc:
        return _handle_error(exc, status="needs_information")


@mcp.tool
def commit_planting_plan(
    client_request_id: str,
    approval_fingerprint: str,
    plan: dict,
) -> dict:
    """提交已经审批的完整种植计划，事务内创建全部业务实体。"""
    try:
        farm_id = require_farm_operation_permission(
            "commit", tool_name="commit_planting_plan"
        )["farm_id"]
        with session_scope() as db:
            return planting_plan_service.commit_planting_plan(
                db,
                farm_id=farm_id,
                client_request_id=client_request_id,
                approval_fingerprint=approval_fingerprint,
                plan=plan,
            )
    except IntegrityError:
        # 并发请求可能同时通过首次查询；唯一键会让后提交者整笔回滚。
        # 回滚后只读取先提交者的结果，绝不保留重复模板、茬口或种植单元。
        try:
            with session_scope() as db:
                replay = planting_plan_service.load_committed_planting_plan(
                    db,
                    farm_id=farm_id,
                    client_request_id=client_request_id,
                    plan=plan,
                )
            if replay is not None:
                return replay
        except planting_plan_service.PlantingPlanError as exc:
            return _handle_error(exc)
        return {
            "status": "failed",
            "error": "planting_plan_rollback",
            "code": "planting_plan_rollback",
            "message": "种植计划提交发生数据库约束冲突，事务已回滚",
        }
    except planting_plan_service.PlantingPlanError as exc:
        return _handle_error(exc)


__all__ = ["prepare_planting_plan", "commit_planting_plan"]
