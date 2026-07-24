import re
from typing import Any

from langchain_core.messages import ToolMessage

from app.agent.reflector import ReflectorService
from app.agent.reflector.models import ReflectionDecision, ReflectionTrigger
from app.agent.router import SkillRouter
from app.agent.runtime.tool_metadata import (
    _PermissionDecision,
    _permission_trace_output,
)
from app.agent.runtime.tool_arg_validation import validate_pending_tool_args
from app.agent.runtime.tool_pending_args import (
    _ambiguous_debt_direction_message,
    _build_pending_confirmation_args,
    _build_pending_execution_args,
    _needs_debt_direction_clarification,
)
from app.agent.state import AgentState
from app.infra.pending_actions import (
    PENDING_MARKER,
    CONTRACT_BLOCKED_MARKER,
    PendingPlanStep,
    WRITE_SKILLS,
    build_confirm_message,
    build_confirmation_context,
    build_plan_confirm_message,
    store_pending,
    store_pending_plan,
)
from app.infra.trace_collector import get_collector

_CROP_VARIETY_RE = re.compile(
    r"(?<!\d)([A-Za-z]*\d+[A-Za-z0-9-]*)(?!\s*(?:亩|元|块|天|号|年|月|日))"
)


def _pending_plan_tool_message(
    *,
    state: AgentState,
    farm_id: int,
    original_input: str,
    tool_calls: list[dict],
) -> list[ToolMessage] | None:
    """如果 router 已生成多步骤写计划，则存储 pending plan 并返回确认消息。"""
    plan_draft = state.get("plan_draft")
    draft_steps = _validated_plan_draft_steps(
        plan_draft,
        expected_route_type="write_pending_plan",
    )
    if draft_steps:
        if _tool_calls_match_plan_steps(tool_calls, draft_steps):
            return _store_pending_plan_from_steps(
                state=state,
                farm_id=farm_id,
                original_input=original_input,
                tool_calls=tool_calls,
                steps=draft_steps,
                router_decision=plan_draft,
                source="plan_draft",
            )

    crop_cycle_steps = _crop_cycle_template_preflight_steps(tool_calls, original_input)
    if crop_cycle_steps:
        return _store_pending_plan_from_steps(
            state=state,
            farm_id=farm_id,
            original_input=original_input,
            tool_calls=tool_calls,
            steps=crop_cycle_steps,
            router_decision=plan_draft if isinstance(plan_draft, dict) else {},
            source="crop_cycle_template_preflight",
        )

    tool_call_steps = _pending_plan_steps_from_tool_calls(tool_calls)
    if tool_call_steps:
        return _store_pending_plan_from_steps(
            state=state,
            farm_id=farm_id,
            original_input=original_input,
            tool_calls=tool_calls,
            steps=tool_call_steps,
            router_decision=plan_draft if isinstance(plan_draft, dict) else {},
            source="tool_calls",
        )

    router_decision = state.get("router_decision")
    if router_decision is None:
        return None

    steps = SkillRouter().build_pending_plan_steps(router_decision)
    if len(steps) < 2:
        return None
    step_tool_names = {str(step["tool_name"]) for step in steps}
    tool_call_names = {str(tool_call["name"]) for tool_call in tool_calls}
    if len(tool_calls) > 1 and not _same_tool_name_sequence(tool_calls, steps):
        return None
    if not tool_call_names.issubset(step_tool_names):
        return None

    return _store_pending_plan_from_steps(
        state=state,
        farm_id=farm_id,
        original_input=original_input,
        tool_calls=tool_calls,
        steps=steps,
        router_decision=router_decision.to_trace_payload(),
        source="router_decision",
    )


def _tool_calls_match_plan_steps(tool_calls: list[dict], steps: list[dict]) -> bool:
    step_tool_names = {str(step["tool_name"]) for step in steps}
    tool_call_names = {str(tool_call["name"]) for tool_call in tool_calls}
    if len(tool_calls) <= 1:
        return tool_call_names.issubset(step_tool_names)
    return _same_tool_name_sequence(tool_calls, steps)


def _same_tool_name_sequence(tool_calls: list[dict], steps: list[dict]) -> bool:
    return [str(tool_call.get("name") or "") for tool_call in tool_calls] == [
        str(step.get("tool_name") or step.get("skill_name") or "") for step in steps
    ]


def _crop_cycle_template_preflight_steps(
    tool_calls: list[dict],
    original_input: str,
) -> list[dict]:
    if len(tool_calls) != 1:
        return []
    tool_call = tool_calls[0]
    if str(tool_call.get("name") or "") != "manage_crop_cycle":
        return []
    args = tool_call.get("args")
    if not isinstance(args, dict):
        return []
    if str(args.get("operation") or "") != "create_cycle":
        return []
    crop_name = str(args.get("crop_name") or "").strip()
    if not crop_name:
        return []

    cycle_params = dict(args)
    cycle_params["operation"] = "create_cycle"
    template_params: dict[str, Any] = {
        "operation": "create_template",
        "crop_name": crop_name,
    }
    variety = _crop_variety_for_template(cycle_params, original_input, crop_name)
    if variety:
        template_params["variety"] = variety

    return [
        {
            "step_id": "ensure_crop_template",
            "tool_name": "manage_crop_templates",
            "params": template_params,
            "depends_on": [],
        },
        {
            "step_id": "create_crop_cycle",
            "tool_name": "manage_crop_cycle",
            "params": cycle_params,
            "depends_on": ["ensure_crop_template"],
        },
    ]


def _crop_variety_for_template(
    cycle_params: dict[str, Any],
    original_input: str,
    crop_name: str,
) -> str | None:
    variety = _clean_crop_variety(cycle_params.get("variety"))
    if variety:
        return variety
    for text in (cycle_params.get("cycle_name"), original_input):
        variety = _extract_crop_variety(str(text or ""), crop_name)
        if variety:
            return variety
    return None


def _extract_crop_variety(text: str, crop_name: str) -> str | None:
    if not text:
        return None
    normalized = (
        text.replace(crop_name, " ")
        .replace("茬口", " ")
        .replace("种植", " ")
        .replace("周期", " ")
    )
    match = _CROP_VARIETY_RE.search(normalized)
    if not match:
        return None
    return _clean_crop_variety(match.group(1))


def _clean_crop_variety(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text


def _pending_plan_steps_from_tool_calls(tool_calls: list[dict]) -> list[dict]:
    if len(tool_calls) < 2:
        return []
    if any(
        str(tool_call.get("name") or "") not in WRITE_SKILLS for tool_call in tool_calls
    ):
        return []
    return [
        {
            "step_id": f"{tool_call['name']}-{index + 1}",
            "tool_name": str(tool_call["name"]),
            "params": dict(tool_call.get("args") or {}),
            "depends_on": [],
        }
        for index, tool_call in enumerate(tool_calls)
    ]


def _store_pending_plan_from_steps(
    *,
    state: AgentState,
    farm_id: int,
    original_input: str,
    tool_calls: list[dict],
    steps: list[dict],
    router_decision: dict,
    source: str,
) -> list[ToolMessage]:
    """根据已验证步骤创建 pending plan。"""
    step_tool_names = {str(step["tool_name"]) for step in steps}
    steps = _steps_with_tool_call_args(steps, tool_calls)
    pending_steps = _pending_steps_from_dicts(steps)
    contract_messages = _pending_plan_contract_messages(
        state=state,
        farm_id=farm_id,
        pending_steps=pending_steps,
        tool_calls=tool_calls,
        router_decision=router_decision,
        source=source,
        original_input=original_input,
    )
    if contract_messages is not None:
        return contract_messages
    confirm_text = build_plan_confirm_message(pending_steps)
    reflection_result = _reflect_pending_plan(
        state=state,
        farm_id=farm_id,
        original_input=original_input,
        tool_calls=tool_calls,
        step_tool_names=step_tool_names,
        pending_steps=pending_steps,
        confirm_text=confirm_text,
        source=source,
    )
    if reflection_result.decision != ReflectionDecision.PASS:
        return _pending_plan_reflection_messages(reflection_result, tool_calls)
    return _store_confirmed_pending_plan_messages(
        state=state,
        farm_id=farm_id,
        original_input=original_input,
        router_decision=router_decision,
        pending_steps=pending_steps,
        tool_calls=tool_calls,
        confirm_text=confirm_text,
    )


def _pending_steps_from_dicts(steps: list[dict]) -> list[PendingPlanStep]:
    return [
        PendingPlanStep(
            step_id=str(step["step_id"]),
            step_index=index,
            tool_name=str(step["tool_name"]),
            params=dict(step.get("params") or {}),
            depends_on=list(step.get("depends_on") or []),
        )
        for index, step in enumerate(steps)
    ]


def _steps_with_tool_call_args(steps: list[dict], tool_calls: list[dict]) -> list[dict]:
    tool_call_args_by_name = _tool_call_args_by_name(tool_calls)
    tool_call_indexes: dict[str, int] = {}
    merged_steps: list[dict] = []
    for step in steps:
        tool_name = str(step.get("tool_name") or step.get("skill_name") or "")
        call_index = tool_call_indexes.get(tool_name, 0)
        tool_call_indexes[tool_name] = call_index + 1
        related_args = _tool_call_args_at(tool_call_args_by_name, tool_name, call_index)
        merged_steps.append(_step_with_missing_params(step, related_args))
    return merged_steps


def _tool_call_args_by_name(tool_calls: list[dict]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for tool_call in tool_calls:
        tool_name = str(tool_call.get("name") or "")
        if not tool_name:
            continue
        args = tool_call.get("args")
        grouped.setdefault(tool_name, []).append(
            dict(args) if isinstance(args, dict) else {}
        )
    return grouped


def _tool_call_args_at(
    grouped_args: dict[str, list[dict[str, Any]]],
    tool_name: str,
    index: int,
) -> dict[str, Any]:
    args_list = grouped_args.get(tool_name) or []
    if index >= len(args_list):
        return {}
    return args_list[index]


def _step_with_missing_params(step: dict, tool_call_args: dict[str, Any]) -> dict:
    if not tool_call_args:
        return step
    params = dict(step.get("params") or {})
    for key, value in tool_call_args.items():
        if _is_missing_param(params.get(key)):
            params[key] = value
    return {**step, "params": params}


def _is_missing_param(value: Any) -> bool:
    return value is None or value == "" or value == []


def _reflect_pending_plan(
    *,
    state: AgentState,
    farm_id: int,
    original_input: str,
    tool_calls: list[dict],
    step_tool_names: set[str],
    pending_steps: list[PendingPlanStep],
    confirm_text: str,
    source: str,
):
    return ReflectorService().check_pending_plan(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        steps=pending_steps,
        confirmation_text=confirm_text,
        trace_metadata={
            "farm_id": farm_id,
            "session_id": state.get("session_id"),
            "raw_user_input": original_input,
            "tool_names": sorted(step_tool_names),
            "tool_call_ids": [str(tool_call["id"]) for tool_call in tool_calls],
            "plan_draft": state.get("plan_draft") or {},
            "pending_source": source,
        },
    )


def _pending_plan_reflection_messages(
    reflection_result,
    tool_calls: list[dict],
) -> list[ToolMessage]:
    return [
        ToolMessage(
            content=reflection_result.reason,
            tool_call_id=tool_call["id"],
        )
        for tool_call in tool_calls
    ]


def _store_confirmed_pending_plan_messages(
    *,
    state: AgentState,
    farm_id: int,
    original_input: str,
    router_decision: dict,
    pending_steps: list[PendingPlanStep],
    tool_calls: list[dict],
    confirm_text: str,
) -> list[ToolMessage]:
    session_id = state.get("session_id")
    store_pending_plan(
        farm_id=farm_id,
        session_id=session_id,
        raw_user_input=original_input,
        router_decision=router_decision,
        steps=pending_steps,
    )
    messages = [
        ToolMessage(
            content="已纳入待确认计划。",
            tool_call_id=tool_call["id"],
        )
        for tool_call in tool_calls
    ]
    messages[0].content = f"{PENDING_MARKER} {confirm_text}"
    return messages


def _pending_plan_contract_messages(
    *,
    state: AgentState,
    farm_id: int,
    pending_steps: list[PendingPlanStep],
    tool_calls: list[dict],
    router_decision: dict,
    source: str,
    original_input: str,
) -> list[ToolMessage] | None:
    """pending plan 创建前逐步校验 operation contract。"""
    blocked = []
    steps_before_validation = _pending_steps_trace_payload(pending_steps)
    for step in pending_steps:
        validation = validate_pending_tool_args(
            skill_name=step.tool_name,
            params=step.params,
            farm_id=farm_id,
        )
        step.params.clear()
        step.params.update(validation.params)
        if validation.valid:
            continue
        blocked.append(
            {
                "step_id": step.step_id,
                "tool_name": step.tool_name,
                "message": validation.message,
                "contract_validation": validation.trace_payload(),
                "params_after_validation": _redact_trace_payload(step.params),
            }
        )
    if not blocked:
        return None

    collector = get_collector()
    tool_calls_payload = _tool_calls_trace_payload(tool_calls)
    steps_after_validation = _pending_steps_trace_payload(pending_steps)
    diagnostics = _pending_plan_contract_diagnostics(
        blocked_steps=blocked,
        tool_calls=tool_calls_payload,
    )
    content = "待确认计划参数不完整：\n" + "\n".join(
        f"{item['step_id']} {item['tool_name']}：{item['message']}" for item in blocked
    )
    collector.record(
        node_type="skill_call",
        node_name="pending_plan",
        input_data={
            "raw_user_input": original_input,
            "source": source,
            "tool_calls": tool_calls_payload,
            "pending_steps_before_validation": steps_before_validation,
            "router_decision": _redact_trace_payload(router_decision),
        },
        output_data={
            "status": "contract_blocked",
            "phase": "create_pending_plan",
            "session_id": state.get("session_id"),
            "blocked_steps": blocked,
            "pending_steps_after_validation": steps_after_validation,
            "diagnostics": diagnostics,
        },
        duration_ms=0,
        error_message=_pending_plan_contract_error_message(blocked),
    )
    return [
        ToolMessage(
            content=f"{CONTRACT_BLOCKED_MARKER} {content}",
            tool_call_id=tool_call["id"],
        )
        for tool_call in tool_calls
    ]


def _validated_plan_draft_steps(
    plan_draft: dict | None,
    *,
    expected_route_type: str,
) -> list[dict]:
    """读取已经通过验证的 PlanDraft 步骤。"""
    if not isinstance(plan_draft, dict):
        return []
    validation = plan_draft.get("validation")
    if not isinstance(validation, dict) or validation.get("status") != "valid":
        return []
    if plan_draft.get("route_type") != expected_route_type:
        return []
    steps = plan_draft.get("steps")
    if not isinstance(steps, list):
        return []
    normalized: list[dict] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            return []
        tool_name = str(step.get("skill_name") or step.get("tool_name") or "")
        params = step.get("params") or {}
        if not tool_name or not isinstance(params, dict):
            return []
        normalized.append(
            {
                "step_id": str(step.get("step_id") or f"step-{index + 1}"),
                "tool_name": tool_name,
                "params": dict(params),
                "depends_on": list(step.get("depends_on") or []),
            }
        )
    return normalized


def _pending_steps_trace_payload(
    pending_steps: list[PendingPlanStep],
) -> list[dict[str, Any]]:
    return [
        {
            "step_id": step.step_id,
            "step_index": step.step_index,
            "tool_name": step.tool_name,
            "params": _redact_trace_payload(step.params),
            "depends_on": list(step.depends_on),
        }
        for step in pending_steps
    ]


def _tool_calls_trace_payload(tool_calls: list[dict]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(tool_call.get("id") or ""),
            "name": str(tool_call.get("name") or ""),
            "args": _redact_trace_payload(dict(tool_call.get("args") or {})),
        }
        for tool_call in tool_calls
    ]


def _pending_plan_contract_diagnostics(
    *,
    blocked_steps: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "param_source_diffs": [
            diff
            for blocked_step in blocked_steps
            if (
                diff := _pending_step_tool_call_diff(
                    blocked_step=blocked_step,
                    tool_calls=tool_calls,
                )
            )
        ]
    }


def _pending_step_tool_call_diff(
    *,
    blocked_step: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any] | None:
    tool_name = str(blocked_step.get("tool_name") or "")
    related_calls = [call for call in tool_calls if call.get("name") == tool_name]
    if not related_calls:
        return None

    validation = blocked_step.get("contract_validation")
    missing_fields = []
    if isinstance(validation, dict):
        missing_fields = [
            str(field) for field in validation.get("missing_fields") or []
        ]

    fields_present_in_tool_calls: dict[str, list[str]] = {}
    for field in missing_fields:
        call_ids = [
            str(call.get("id") or "")
            for call in related_calls
            if _trace_args_has_field(call.get("args"), field)
        ]
        if call_ids:
            fields_present_in_tool_calls[field] = call_ids

    if not fields_present_in_tool_calls:
        return {
            "step_id": blocked_step.get("step_id"),
            "tool_name": tool_name,
            "related_tool_call_ids": [call["id"] for call in related_calls],
            "missing_fields": missing_fields,
            "diagnosis": "pending_step_and_tool_calls_missing_required_fields",
        }

    return {
        "step_id": blocked_step.get("step_id"),
        "tool_name": tool_name,
        "related_tool_call_ids": [call["id"] for call in related_calls],
        "missing_fields": missing_fields,
        "fields_present_in_tool_calls": fields_present_in_tool_calls,
        "diagnosis": "pending_step_missing_field_present_in_llm_tool_call",
    }


def _trace_args_has_field(args: Any, field: str) -> bool:
    if not isinstance(args, dict):
        return False
    value = args.get(field)
    return value is not None and value != ""


def _pending_plan_contract_error_message(blocked: list[dict[str, Any]]) -> str:
    details = "; ".join(
        f"{item['step_id']} {item['tool_name']}: {item['message']}" for item in blocked
    )
    return f"pending plan contract blocked: {details}"


_SENSITIVE_TRACE_KEYS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}


def _redact_trace_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if _is_sensitive_trace_key(key)
            else _redact_trace_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_trace_payload(item) for item in value]
    return value


def _is_sensitive_trace_key(key: Any) -> bool:
    return str(key).strip().lower() in _SENSITIVE_TRACE_KEYS


def _validated_plan_draft_action_args(
    plan_draft: dict | None,
    *,
    tool_name: str,
) -> dict | None:
    """读取已验证单步写 PlanDraft 的执行参数。"""
    steps = _validated_plan_draft_steps(
        plan_draft,
        expected_route_type="write_pending_action",
    )
    if len(steps) != 1:
        return None
    step = steps[0]
    if step["tool_name"] != tool_name:
        return None
    return dict(step["params"])


def _resolve_pending_execution_args(
    *,
    state: AgentState,
    name: str,
    args: dict,
    farm_id: int,
    original_input: str,
) -> dict:
    execution_args = _validated_plan_draft_action_args(
        state.get("plan_draft"),
        tool_name=name,
    )
    if execution_args is not None:
        return _build_pending_execution_args(
            name, execution_args, farm_id, original_input
        )
    return _build_pending_execution_args(name, args, farm_id, original_input)


def _ambiguous_pending_message(
    *,
    name: str,
    execution_args: dict,
    original_input: str,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    ambiguous_debt_name = _needs_debt_direction_clarification(
        name, execution_args, original_input
    )
    if not ambiguous_debt_name:
        return None
    content = _ambiguous_debt_direction_message(
        ambiguous_debt_name,
        execution_args,
    )
    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=execution_args,
        output_data={
            "status": "need_clarify",
            "reason": "ambiguous_debt_direction",
            **_permission_trace_output(permission_decision),
        },
        duration_ms=0,
    )
    return ToolMessage(
        content=content,
        tool_call_id=tool_call_id,
    )


def _build_pending_confirmation(
    *,
    name: str,
    execution_args: dict,
    farm_id: int,
    original_input: str,
) -> tuple[dict, str]:
    confirmation_args = _build_pending_confirmation_args(name, execution_args, farm_id)
    confirmation_context = build_confirmation_context(
        name, confirmation_args, original_input=original_input
    )
    confirm_text = build_confirm_message(
        name, confirmation_args, original_input=original_input
    )
    return confirmation_context, confirm_text


def _reflection_block_message(
    *,
    state: AgentState,
    name: str,
    execution_args: dict,
    confirm_text: str,
    farm_id: int,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    reflection_result = ReflectorService().check_write_plan(
        trigger=ReflectionTrigger.PRE_WRITE_PLAN,
        skill_name=name,
        params=execution_args,
        confirmation_text=confirm_text,
        trace_metadata={
            "farm_id": farm_id,
            "session_id": state.get("session_id"),
            "tool_name": name,
            "tool_call_id": tool_call_id,
            "plan_draft": state.get("plan_draft") or {},
        },
    )
    if reflection_result.decision == ReflectionDecision.PASS:
        return None
    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=execution_args,
        output_data={
            "status": "reflection_blocked",
            "reflection": reflection_result.to_trace_payload(),
            **_permission_trace_output(permission_decision),
        },
        duration_ms=0,
    )
    return ToolMessage(
        content=reflection_result.reason,
        tool_call_id=tool_call_id,
    )


def _store_pending_action_message(
    *,
    state: AgentState,
    name: str,
    execution_args: dict,
    original_input: str,
    confirmation_context: dict,
    confirm_text: str,
    farm_id: int,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
    logger,
) -> ToolMessage:
    session_id = state.get("session_id")
    action_id = store_pending(
        farm_id,
        name,
        execution_args,
        original_input=original_input,
        confirmation_context=confirmation_context,
        session_id=session_id,
    )
    logger.info(
        "写操作 Skill 已拦截 | farm=%s action_id=%s skill=%s",
        farm_id,
        action_id,
        name,
    )
    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=execution_args,
        output_data={
            "status": "pending",
            "confirmation_context": confirmation_context,
            "plan_draft": state.get("plan_draft") or {},
            **_permission_trace_output(permission_decision),
        },
        duration_ms=0,
    )
    return ToolMessage(
        content=f"{PENDING_MARKER} {confirm_text}",
        tool_call_id=tool_call_id,
    )


def _pending_action_message(
    *,
    state: AgentState,
    name: str,
    args: dict,
    farm_id: int,
    original_input: str,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
    logger,
) -> ToolMessage | None:
    """写操作 Skill 拦截：存储 pending action，不直接执行。"""
    if not permission_decision.requires_confirmation:
        return None
    execution_args = _resolve_pending_execution_args(
        state=state,
        name=name,
        args=args,
        farm_id=farm_id,
        original_input=original_input,
    )
    blocking_message, confirmation_context, confirm_text = _pending_action_precheck(
        state=state,
        name=name,
        execution_args=execution_args,
        original_input=original_input,
        farm_id=farm_id,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if blocking_message is not None:
        return blocking_message
    return _store_pending_action_message(
        state=state,
        name=name,
        execution_args=execution_args,
        original_input=original_input,
        confirmation_context=confirmation_context or {},
        confirm_text=confirm_text or "",
        farm_id=farm_id,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
        logger=logger,
    )


def _pending_action_precheck(
    *,
    state: AgentState,
    name: str,
    execution_args: dict,
    original_input: str,
    farm_id: int,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> tuple[ToolMessage | None, dict | None, str | None]:
    ambiguous_message = _ambiguous_pending_message(
        name=name,
        execution_args=execution_args,
        original_input=original_input,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if ambiguous_message is not None:
        return ambiguous_message, None, None
    contract_validation = validate_pending_tool_args(
        skill_name=name,
        params=execution_args,
        farm_id=farm_id,
        original_input=original_input,
    )
    execution_args.clear()
    execution_args.update(contract_validation.params)
    if not contract_validation.valid:
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=execution_args,
            output_data={
                "status": "contract_blocked",
                "contract_validation": contract_validation.trace_payload(),
                "plan_draft": state.get("plan_draft") or {},
                **_permission_trace_output(permission_decision),
            },
            duration_ms=0,
        )
        return (
            ToolMessage(
                content=f"{CONTRACT_BLOCKED_MARKER} {contract_validation.message}",
                tool_call_id=tool_call_id,
            ),
            None,
            None,
        )
    confirmation_context, confirm_text = _build_pending_confirmation(
        name=name,
        execution_args=execution_args,
        farm_id=farm_id,
        original_input=original_input,
    )
    reflection_message = _reflection_block_message(
        state=state,
        name=name,
        execution_args=execution_args,
        confirm_text=confirm_text,
        farm_id=farm_id,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if reflection_message is not None:
        return reflection_message, None, None
    return None, confirmation_context, confirm_text


__all__ = ["_pending_action_message", "_pending_plan_tool_message"]
