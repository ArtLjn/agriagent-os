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
    build_confirm_message,
    build_confirmation_context,
    build_plan_confirm_message,
    store_pending,
    store_pending_plan,
)
from app.infra.trace_collector import get_collector


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
        step_tool_names = {str(step["tool_name"]) for step in draft_steps}
        tool_call_names = {str(tool_call["name"]) for tool_call in tool_calls}
        if tool_call_names.issubset(step_tool_names):
            return _store_pending_plan_from_steps(
                state=state,
                farm_id=farm_id,
                original_input=original_input,
                tool_calls=tool_calls,
                steps=draft_steps,
                router_decision=plan_draft,
                source="plan_draft",
            )

    router_decision = state.get("router_decision")
    if router_decision is None:
        return None

    steps = SkillRouter().build_pending_plan_steps(router_decision)
    if len(steps) < 2:
        return None
    step_tool_names = {str(step["tool_name"]) for step in steps}
    tool_call_names = {str(tool_call["name"]) for tool_call in tool_calls}
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
    pending_steps = _pending_steps_from_dicts(steps)
    contract_messages = _pending_plan_contract_messages(
        state=state,
        farm_id=farm_id,
        pending_steps=pending_steps,
        tool_calls=tool_calls,
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
) -> list[ToolMessage] | None:
    """pending plan 创建前逐步校验 operation contract。"""
    blocked = []
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
            }
        )
    if not blocked:
        return None

    collector = get_collector()
    collector.record(
        node_type="skill_call",
        node_name="pending_plan",
        input_data={"steps": [step.__dict__ for step in pending_steps]},
        output_data={
            "status": "contract_blocked",
            "phase": "create_pending_plan",
            "session_id": state.get("session_id"),
            "blocked_steps": blocked,
        },
        duration_ms=0,
    )
    content = "待确认计划参数不完整：\n" + "\n".join(
        f"{item['step_id']} {item['tool_name']}：{item['message']}" for item in blocked
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
