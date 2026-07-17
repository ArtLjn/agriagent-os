"""Agent Runtime 工具 metadata、权限与结果辅助。"""

import time as _time
from dataclasses import dataclass

from langchain_core.messages import ToolMessage

from app.agent.state import AgentState
from app.infra.pending_actions import is_write_skill_call
from app.skills.metadata import (
    SkillPermissionLevel,
    resolve_skill_capability_metadata,
)


@dataclass(frozen=True)
class _PermissionDecision:
    permission_level: str
    requires_confirmation: bool = False
    reject_message: str | None = None
    disabled: bool = False
    disabled_reason: str | None = None
    legacy_alias: str | None = None
    capability: str | None = None
    operation: str | None = None
    operation_risk: str | None = None
    registry_enabled: bool | None = None
    registry_disabled_reason: str | None = None

    @property
    def is_disabled(self) -> bool:
        return self.disabled


_KNOWN_PERMISSION_LEVELS = {level.value for level in SkillPermissionLevel}
_LABOR_PAYMENT_SKILL = "manage_labor_payment"
_LABOR_SETTLE_OPERATION = "settle_payment"
_LABOR_QUERY_OPERATION = "query_payables"
_LABOR_WAGE_OPERATION = "manage_wage"
_LABOR_PAYMENT_SETTLE_FIELDS = ("amount", "scope", "payment_date")
_LABOR_PAYMENT_WAGE_FIELDS = (
    "action",
    "labor_entry_id",
    "operation_type",
    "worker_id",
    "pay_type",
    "quantity",
    "unit_price",
    "paid_amount",
    "note",
    "work_date",
    "client_request_id",
)


def _permission_decision(
    tool,
    skill_name: str,
    state: AgentState,
    args: dict | None = None,
) -> _PermissionDecision:
    """根据 metadata 权限等级做执行决策，未知权限按 fail closed 处理。"""
    metadata = getattr(tool, "skill_metadata", None)
    capability_metadata = _capability_metadata_from_runtime(metadata, skill_name, args)
    permission_value = (
        _metadata_permission_value(metadata) if metadata is not None else None
    )
    if capability_metadata.get("registry_enabled") is False:
        return _registry_disabled_permission_decision(
            permission_value,
            skill_name,
            capability_metadata,
        )
    if metadata is None:
        return _legacy_permission_decision(skill_name, capability_metadata)

    if getattr(metadata, "enabled", None) is False:
        return _disabled_permission_decision(
            permission_value,
            skill_name,
            getattr(metadata, "disabled_reason", None),
            capability_metadata,
        )
    if _must_honor_metadata_permission_before_operation(
        permission_value,
        skill_name,
        capability_metadata,
    ):
        return _metadata_permission_decision(
            permission_value,
            skill_name,
            state,
            capability_metadata,
        )
    operation_decision = _operation_risk_decision(capability_metadata)
    if operation_decision is not None:
        return operation_decision
    return _metadata_permission_decision(
        permission_value,
        skill_name,
        state,
        capability_metadata,
    )


def _metadata_permission_value(metadata):
    permission_level = getattr(metadata, "permission_level", None)
    return getattr(permission_level, "value", permission_level)


def _must_honor_metadata_permission_before_operation(
    permission_value,
    skill_name: str,
    capability_metadata: dict,
) -> bool:
    if permission_value == SkillPermissionLevel.ADMIN.value:
        return True
    if permission_value == SkillPermissionLevel.WRITE_CONFIRM.value:
        return capability_metadata.get("operation_risk") != SkillPermissionLevel.READ.value
    if permission_value in {SkillPermissionLevel.EXTERNAL_NETWORK.value}:
        return True
    return isinstance(permission_value, str) and (
        permission_value not in _KNOWN_PERMISSION_LEVELS
        and not is_write_skill_call(skill_name, None)
    )


def _registry_disabled_permission_decision(
    permission_value,
    skill_name: str,
    capability_metadata: dict,
) -> _PermissionDecision:
    return _disabled_permission_decision(
        permission_value,
        skill_name,
        capability_metadata.get("registry_disabled_reason") or "Registry disabled",
        capability_metadata,
    )


def _disabled_permission_decision(
    permission_value,
    skill_name: str,
    disabled_reason: str | None,
    capability_metadata: dict,
) -> _PermissionDecision:
    return _PermissionDecision(
        permission_level=_permission_value_for_disabled(
            permission_value,
            skill_name,
            capability_metadata.get("operation_risk"),
        ),
        disabled=True,
        disabled_reason=disabled_reason,
        **capability_metadata,
    )


def _metadata_permission_decision(
    permission_value,
    skill_name: str,
    state: AgentState,
    capability_metadata: dict,
) -> _PermissionDecision:
    if permission_value in _KNOWN_PERMISSION_LEVELS:
        return _known_permission_decision(permission_value, state, capability_metadata)
    if isinstance(permission_value, str):
        if is_write_skill_call(skill_name, None):
            return _write_confirm_decision(capability_metadata)
        return _PermissionDecision(
            permission_level=permission_value,
            reject_message="工具调用失败：未知权限等级。",
            **capability_metadata,
        )
    return _legacy_permission_decision(skill_name, capability_metadata)


def _known_permission_decision(
    permission_value: str,
    state: AgentState,
    capability_metadata: dict,
) -> _PermissionDecision:
    if permission_value == SkillPermissionLevel.WRITE_CONFIRM.value:
        return _write_confirm_decision(capability_metadata)
    if permission_value == SkillPermissionLevel.ADMIN.value:
        if state.get("user_role") == "admin":
            return _PermissionDecision(
                permission_level=permission_value,
                **capability_metadata,
            )
        return _PermissionDecision(
            permission_level=permission_value,
            reject_message="工具调用失败：需要管理员权限。",
            **capability_metadata,
        )
    return _PermissionDecision(permission_level=permission_value, **capability_metadata)


def _legacy_permission_decision(
    skill_name: str,
    capability_metadata: dict,
) -> _PermissionDecision:
    if is_write_skill_call(skill_name, None):
        return _write_confirm_decision(capability_metadata)

    return _PermissionDecision(
        permission_level=SkillPermissionLevel.READ.value,
        **capability_metadata,
    )


def _write_confirm_decision(capability_metadata: dict) -> _PermissionDecision:
    return _PermissionDecision(
        permission_level=SkillPermissionLevel.WRITE_CONFIRM.value,
        requires_confirmation=True,
        **capability_metadata,
    )


def _capability_metadata_from_runtime(
    metadata,
    skill_name: str,
    args: dict | None = None,
) -> dict:
    """读取 Tool metadata；缺失时用 Registry alias 做兼容解析。"""
    operation_name = _operation_name_from_args(skill_name, args)
    resolved = resolve_skill_capability_metadata(skill_name, operation_name) or {}
    operation = resolved.get("operation") or getattr(metadata, "operation", None)
    operation_risk = resolved.get("operation_risk") or getattr(
        metadata,
        "operation_risk",
        None,
    )
    return {
        "legacy_alias": getattr(metadata, "legacy_alias", None)
        or resolved.get("legacy_alias"),
        "capability": getattr(metadata, "capability", None)
        or resolved.get("capability"),
        "operation": operation,
        "operation_risk": operation_risk,
        "registry_enabled": resolved.get("enabled"),
        "registry_disabled_reason": resolved.get("disabled_reason"),
    }


def _operation_name_from_args(skill_name: str, args: dict | None) -> str | None:
    if not isinstance(args, dict):
        args = {}
    operation = args.get("operation")
    if operation:
        return str(operation)
    resolved = resolve_skill_capability_metadata(skill_name)
    if resolved is not None and resolved.get("operation"):
        return str(resolved["operation"])
    if skill_name == _LABOR_PAYMENT_SKILL:
        return _labor_payment_operation_from_args(args)
    if skill_name == "manage_user_settings":
        write_fields = (
            "display_name",
            "default_city",
            "default_lat",
            "default_lon",
            "assistant_role",
        )
        return (
            "update_settings"
            if any(args.get(key) is not None for key in write_fields)
            else "query_settings"
        )
    return None


def _labor_payment_operation_from_args(args: dict) -> str | None:
    has_settle_fields = any(
        args.get(key) not in (None, "") for key in _LABOR_PAYMENT_SETTLE_FIELDS
    )
    has_wage_fields = any(
        args.get(key) not in (None, "") for key in _LABOR_PAYMENT_WAGE_FIELDS
    )
    if has_settle_fields and _only_labor_payment_worker_id_wage_field(args):
        return _LABOR_SETTLE_OPERATION
    if has_settle_fields and has_wage_fields:
        return None
    if has_settle_fields:
        return _LABOR_SETTLE_OPERATION
    if has_wage_fields:
        return _LABOR_WAGE_OPERATION
    return _LABOR_QUERY_OPERATION


def _only_labor_payment_worker_id_wage_field(args: dict) -> bool:
    wage_keys = {
        key
        for key in _LABOR_PAYMENT_WAGE_FIELDS
        if args.get(key) not in (None, "")
    }
    return wage_keys == {"worker_id"}


def _permission_value_for_disabled(
    permission_value,
    skill_name: str,
    operation_risk: str | None,
) -> str:
    if permission_value in _KNOWN_PERMISSION_LEVELS:
        return permission_value
    if operation_risk == SkillPermissionLevel.EXTERNAL_NETWORK.value:
        return SkillPermissionLevel.EXTERNAL_NETWORK.value
    if operation_risk in {"write_confirm", "write_high"}:
        return SkillPermissionLevel.WRITE_CONFIRM.value
    if operation_risk == SkillPermissionLevel.READ.value:
        return SkillPermissionLevel.READ.value
    if is_write_skill_call(skill_name, None):
        return SkillPermissionLevel.WRITE_CONFIRM.value
    if isinstance(permission_value, str):
        return permission_value
    return SkillPermissionLevel.READ.value


def _operation_risk_decision(
    capability_metadata: dict,
) -> _PermissionDecision | None:
    operation_risk = capability_metadata.get("operation_risk")
    if operation_risk == SkillPermissionLevel.EXTERNAL_NETWORK.value:
        return _PermissionDecision(
            permission_level=SkillPermissionLevel.EXTERNAL_NETWORK.value,
            **capability_metadata,
        )
    if operation_risk in {"write_confirm", "write_high"}:
        return _PermissionDecision(
            permission_level=SkillPermissionLevel.WRITE_CONFIRM.value,
            requires_confirmation=True,
            **capability_metadata,
        )
    if operation_risk == SkillPermissionLevel.READ.value:
        return _PermissionDecision(
            permission_level=SkillPermissionLevel.READ.value,
            **capability_metadata,
        )
    return None


def _permission_trace_output(permission_decision: _PermissionDecision) -> dict:
    payload = {"permission_level": permission_decision.permission_level}
    if permission_decision.legacy_alias:
        payload["legacy_tool_name"] = permission_decision.legacy_alias
    if permission_decision.capability:
        payload["resolved_capability"] = permission_decision.capability
    if permission_decision.operation:
        payload["resolved_operation"] = permission_decision.operation
    if permission_decision.operation_risk:
        payload["operation_risk"] = permission_decision.operation_risk
    return payload


def _success_trace_output(result, permission_decision: _PermissionDecision) -> dict:
    """组装工具成功 trace metadata。"""
    trace_output = getattr(result, "trace_data", None)
    if not trace_output:
        trace_output = {
            "status": "success",
            "reply_preview": str(result)[:500],
        }
    else:
        trace_output["reply_preview"] = str(result)[:500]
    trace_output.update(_permission_trace_output(permission_decision))
    return trace_output


def _tool_message_kwargs(name: str, args: dict) -> dict:
    if name in {"manage_cost", "manage_farm_logs", "manage_work_orders"} and args.get(
        "operation"
    ):
        return {"operation": str(args["operation"])}
    return {}


def _runtime_tool_for_call(name: str, args: dict, tool_map: dict):
    """按 registry alias 解析实际 runtime tool。"""
    resolved = resolve_skill_capability_metadata(name, args.get("operation")) or {}
    canonical_name = resolved.get("capability") or name
    return tool_map.get(name) or tool_map.get(canonical_name)


def _execution_args_for_call(name: str, args: dict) -> dict:
    """为 legacy alias 调用补齐 registry operation。"""
    execution_args = dict(args or {})
    resolved = resolve_skill_capability_metadata(
        name,
        execution_args.get("operation"),
    )
    if resolved is not None and resolved.get("operation"):
        execution_args.setdefault("operation", resolved["operation"])
    return execution_args


async def _invoke_read_tool_message(
    *,
    tool,
    name: str,
    args: dict,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
    start: float,
    logger,
) -> ToolMessage:
    """执行读操作工具并记录结果 metadata。"""
    if not tool:
        return ToolMessage(content=f"未知工具: {name}", tool_call_id=tool_call_id)
    try:
        result = await tool.ainvoke(args)
        duration_ms = int((_time.perf_counter() - start) * 1000)
        logger.info(
            "Skill 完成 | name=%s | duration_ms=%d | result=%s",
            name,
            duration_ms,
            str(result)[:120].replace("\n", " "),
        )
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=args,
            output_data=_success_trace_output(result, permission_decision),
            duration_ms=duration_ms,
        )
        return ToolMessage(
            content=str(result),
            tool_call_id=tool_call_id,
            name=name,
            additional_kwargs=_tool_message_kwargs(name, args),
        )
    except Exception as e:
        duration_ms = int((_time.perf_counter() - start) * 1000)
        logger.error(
            "Skill 失败 | name=%s | error=%s",
            name,
            e,
        )
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=args,
            duration_ms=duration_ms,
            error_message=str(e),
        )
        return ToolMessage(content=f"工具调用失败: {e}", tool_call_id=tool_call_id)


__all__ = [
    "_LABOR_PAYMENT_SKILL",
    "_LABOR_QUERY_OPERATION",
    "_LABOR_SETTLE_OPERATION",
    "_PermissionDecision",
    "_execution_args_for_call",
    "_invoke_read_tool_message",
    "_operation_name_from_args",
    "_permission_decision",
    "_permission_trace_output",
    "_runtime_tool_for_call",
]
