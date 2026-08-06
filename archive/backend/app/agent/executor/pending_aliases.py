"""Pending action legacy alias 解析。"""

from app.skills.metadata import resolve_skill_capability_metadata
from app.infra.trace_collector import get_collector


def pending_alias_metadata(skill_name: str, params: dict | None = None) -> dict:
    """解析历史 pending action 的 legacy skill name，缺失时 fail closed。"""
    operation_name = params.get("operation") if isinstance(params, dict) else None
    metadata = resolve_skill_capability_metadata(skill_name, operation_name)
    if metadata is None:
        raise ValueError(f"未知 legacy alias，已拒绝执行：{skill_name}")
    if metadata.get("enabled") is False:
        reason = metadata.get("disabled_reason") or "Capability 已禁用"
        raise ValueError(f"Skill 已禁用，已拒绝执行：{skill_name}。原因：{reason}")
    return {
        "legacy_tool_name": metadata["legacy_alias"] or skill_name,
        "resolved_capability": metadata["capability"],
        "resolved_operation": metadata["operation"],
        "operation_risk": metadata["operation_risk"],
    }


def pending_alias_metadata_or_trace(skill_name: str, params: dict) -> dict:
    """解析 alias；失败时记录 missing alias trace 后抛出。"""
    try:
        return pending_alias_metadata(skill_name, params)
    except ValueError as exc:
        get_collector().record(
            node_type="skill_call",
            node_name=skill_name,
            input_data=params,
            output_data={
                "status": "failed",
                "legacy_tool_name": skill_name,
                "alias_resolution": "missing",
            },
            error_message=str(exc),
        )
        raise
