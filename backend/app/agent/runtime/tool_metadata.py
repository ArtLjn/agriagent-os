"""Agent Runtime 工具 metadata、权限与结果辅助。"""

import time as _time
from dataclasses import dataclass

from langchain_core.messages import ToolMessage

from app.agent.state import AgentState
from app.infra.pending_actions import is_write_skill_call
from app.skills.metadata import (
    SkillPermissionLevel,
    infer_skill_operation_name,
    resolve_skill_capability_metadata,
)
from app.skills.registry import load_skill_registry


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
    invalid_operation: str | None = None
    missing_required_target_fields: list[str] | None = None

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
_WRITE_OPERATION_RISKS = frozenset({"write_confirm", "write_high"})
_IGNORED_TARGET_FIELDS = frozenset({"operation", "action", "skill_name"})
_TARGET_FALLBACK_FIELDS = frozenset(
    {
        "id",
        "worker_id",
        "worker",
        "worker_name",
        "name",
        "scope",
        "cycle_id",
        "cycle_name",
        "record_id",
        "category_id",
        "template_id",
        "unit_id",
        "log_id",
        "work_order_id",
        "labor_entry_id",
        "counterparty",
    }
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
    invalid_operation_decision = _invalid_operation_permission_decision(
        capability_metadata
    )
    if invalid_operation_decision is not None:
        return invalid_operation_decision
    missing_target_decision = _missing_required_target_permission_decision(
        metadata,
        args,
        capability_metadata,
    )
    if missing_target_decision is not None:
        return missing_target_decision
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
    mixed_operation_decision = _mixed_operation_write_guard_decision(
        skill_name,
        args,
        capability_metadata,
    )
    if mixed_operation_decision is not None:
        return mixed_operation_decision
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
        return (
            capability_metadata.get("operation_risk") != SkillPermissionLevel.READ.value
        )
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
    invalid_operation = _invalid_explicit_operation_name(skill_name, args)
    ignore_default_operation = (
        invalid_operation is not None
        or (
            operation_name is None
            and _is_registry_capability_name(skill_name)
            and _capability_has_write_operations(skill_name)
        )
    )
    resolved = (
        {}
        if invalid_operation is not None
        else resolve_skill_capability_metadata(skill_name, operation_name) or {}
    )
    if ignore_default_operation:
        operation = None
        operation_risk = None
    else:
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
        or resolved.get("capability")
        or _registry_capability_name_for_skill(skill_name),
        "operation": operation,
        "operation_risk": operation_risk,
        "registry_enabled": resolved.get("enabled"),
        "registry_disabled_reason": resolved.get("disabled_reason"),
        "invalid_operation": invalid_operation,
    }


def _operation_name_from_args(skill_name: str, args: dict | None) -> str | None:
    if not isinstance(args, dict):
        args = {}
    operation = args.get("operation")
    if operation:
        return str(operation)
    inferred = infer_skill_operation_name(skill_name, args)
    if inferred:
        if (
            _has_meaningful_args(args)
            or _alias_default_operation_name(skill_name) is None
        ):
            return inferred
    else:
        if _is_registry_capability_name(
            skill_name
        ) and _capability_has_write_operations(skill_name):
            return None
    resolved = resolve_skill_capability_metadata(skill_name)
    if resolved is not None and resolved.get("operation"):
        return str(resolved["operation"])
    if inferred:
        return inferred
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


def _mixed_operation_write_guard_decision(
    skill_name: str,
    args: dict | None,
    capability_metadata: dict,
) -> _PermissionDecision | None:
    if capability_metadata.get("operation") or not _has_meaningful_args(args):
        return None
    if (
        not _is_registry_capability_name(skill_name)
        and _alias_default_operation_name(skill_name) is not None
    ):
        return None
    if not _capability_has_write_operations(skill_name):
        return None
    guarded_metadata = {
        **capability_metadata,
        "operation_risk": SkillPermissionLevel.WRITE_CONFIRM.value,
    }
    return _write_confirm_decision(guarded_metadata)


def _invalid_operation_permission_decision(
    capability_metadata: dict,
) -> _PermissionDecision | None:
    invalid_operation = capability_metadata.get("invalid_operation")
    if invalid_operation is None:
        return None
    return _PermissionDecision(
        permission_level=SkillPermissionLevel.READ.value,
        reject_message=f"工具调用失败：未知 operation「{invalid_operation}」。",
        **capability_metadata,
    )


def _missing_required_target_permission_decision(
    metadata,
    args: dict | None,
    capability_metadata: dict,
) -> _PermissionDecision | None:
    if capability_metadata.get("operation_risk") not in _WRITE_OPERATION_RISKS:
        return None
    missing_fields = _missing_required_target_fields(metadata, args)
    if not missing_fields:
        return None
    return _PermissionDecision(
        permission_level=SkillPermissionLevel.READ.value,
        reject_message="工具调用失败：写操作缺少明确目标，请补充要操作的对象。",
        missing_required_target_fields=missing_fields,
        **capability_metadata,
    )


def _missing_required_target_fields(metadata, args: dict | None) -> list[str]:
    if not isinstance(args, dict):
        args = {}
    confirmation_schema = getattr(metadata, "confirmation_schema", None)
    target_fields = list(getattr(confirmation_schema, "target_fields", None) or [])
    required_targets = [
        field for field in target_fields if field not in _IGNORED_TARGET_FIELDS
    ]
    if not required_targets:
        return []
    accepted_targets = set(required_targets) | _TARGET_FALLBACK_FIELDS
    if any(args.get(field) not in (None, "", [], {}) for field in accepted_targets):
        return []
    return required_targets


def _has_meaningful_args(args: dict | None) -> bool:
    if not isinstance(args, dict):
        return False
    return any(
        key != "operation" and value not in (None, "", [], {})
        for key, value in args.items()
    )


def _is_registry_capability_name(skill_name: str) -> bool:
    try:
        registry = load_skill_registry()
    except (OSError, ValueError):
        return False
    return skill_name in registry.capabilities


def _alias_default_operation_name(skill_name: str) -> str | None:
    try:
        registry = load_skill_registry()
    except (OSError, ValueError):
        return None
    alias = registry.resolve_alias(skill_name)
    return alias.operation if alias is not None else None


def _invalid_explicit_operation_name(
    skill_name: str,
    args: dict | None,
) -> str | None:
    if not isinstance(args, dict) or not args.get("operation"):
        return None
    operation_name = str(args["operation"])
    try:
        registry = load_skill_registry()
    except (OSError, ValueError):
        return None
    capability_name = _registry_capability_name_for_skill(skill_name, registry)
    capability = registry.capabilities.get(capability_name or "")
    if capability is None:
        return None
    return None if operation_name in capability.operations else operation_name


def _registry_capability_name_for_skill(skill_name: str, registry=None) -> str | None:
    if registry is None:
        try:
            registry = load_skill_registry()
        except (OSError, ValueError):
            return None
    alias = registry.resolve_alias(skill_name)
    if alias is not None:
        return alias.capability
    if skill_name in registry.capabilities:
        return skill_name
    return None


def _capability_has_write_operations(skill_name: str) -> bool:
    try:
        registry = load_skill_registry()
    except (OSError, ValueError):
        return False
    alias = registry.resolve_alias(skill_name)
    capability_name = alias.capability if alias is not None else skill_name
    capability = registry.capabilities.get(capability_name)
    if capability is None:
        return False
    return any(
        operation.risk in _WRITE_OPERATION_RISKS
        for operation in capability.operations.values()
    )


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
        key for key in _LABOR_PAYMENT_WAGE_FIELDS if args.get(key) not in (None, "")
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
    if permission_decision.invalid_operation:
        payload["invalid_operation"] = permission_decision.invalid_operation
    if permission_decision.missing_required_target_fields:
        payload["missing_required_target_fields"] = (
            permission_decision.missing_required_target_fields
        )
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
    if execution_args.get("operation"):
        return execution_args
    inferred = infer_skill_operation_name(name, execution_args)
    if inferred:
        if (
            _has_meaningful_args(execution_args)
            or _alias_default_operation_name(name) is None
        ):
            execution_args.setdefault("operation", inferred)
            return execution_args
    else:
        if _is_registry_capability_name(name) and _capability_has_write_operations(
            name
        ):
            return execution_args
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
        logger.error("Skill 失败 | name=%s | error=%s", name, e)
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
