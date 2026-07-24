"""Agent Runtime 工具执行。"""

import asyncio
import logging
import time as _time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.state import AgentState
from app.agent.runtime.tool_metadata import (
    _PermissionDecision,
    _execution_args_for_call,
    _invoke_read_tool_message,
    _permission_decision,
    _permission_trace_output,
    _runtime_tool_for_call,
)
from app.agent.runtime import tool_pending as _tool_pending
from app.agent.runtime import tool_pending_args as _tool_pending_args
from app.skills import get_langchain_tools
from app.infra.trace_collector import get_collector
from app.infra.trace_context import set_round_index
from app.shared.logging import log_event

logger = logging.getLogger(__name__)


def _latest_human_input(state: AgentState) -> str:
    """获取最近一条用户输入，保持原有 200 字截断。"""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content[:200]
    return ""


def _record_pending_plan_trace(collector, original_input: str) -> None:
    collector.record(
        node_type="skill_call",
        node_name="pending_plan",
        input_data={"message": original_input},
        output_data={"status": "pending_plan"},
        duration_ms=0,
    )


def _disabled_tool_message(
    *,
    name: str,
    args: dict,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    """如果工具被禁用，记录 trace 并返回失败消息。"""
    if not permission_decision.is_disabled:
        return None

    output_data = {
        "status": "disabled",
        **_permission_trace_output(permission_decision),
    }
    content = "工具调用失败：工具已禁用。"
    if permission_decision.disabled_reason:
        output_data["disabled_reason"] = permission_decision.disabled_reason
        content = f"{content} 原因：{permission_decision.disabled_reason}"
    log_event(
        logger,
        logging.WARNING,
        "tool_disabled",
        code="tool_disabled",
        step_id=f"tool-call-{tool_call_id}",
        status="blocked",
        data={
            "tool": name,
            "permission_level": permission_decision.permission_level,
            "disabled_reason": permission_decision.disabled_reason,
        },
    )
    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=args,
        output_data=output_data,
        duration_ms=0,
    )
    return ToolMessage(
        content=content,
        tool_call_id=tool_call_id,
    )


def _validation_error_message(
    *,
    tool,
    name: str,
    args: dict,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    """执行 Pydantic 参数校验，失败时反馈 LLM 自纠错。"""
    if not (tool and hasattr(tool, "args_schema") and tool.args_schema):
        return None
    try:
        tool.args_schema.model_validate(args)
    except Exception as e:
        error_msg = f"参数校验失败: {e}"
        log_event(
            logger,
            logging.WARNING,
            "tool_args_validation_error",
            code="tool_args_validation_error",
            step_id=f"tool-call-{tool_call_id}",
            status="failed",
            data={
                "tool": name,
                "error": str(e),
            },
            error={
                "type": "tool_args_validation_error",
                "message": str(e),
                "recover": "ask_llm_to_repair_tool_args",
            },
        )
        collector.record(
            node_type="skill_call",
            node_name=name,
            input_data=args,
            output_data={
                "status": "validation_error",
                **_permission_trace_output(permission_decision),
            },
            duration_ms=0,
            error_message=str(e),
        )
        return ToolMessage(
            content=error_msg,
            tool_call_id=tool_call_id,
        )
    return None


def _permission_reject_message(
    *,
    name: str,
    args: dict,
    tool_call_id: str,
    permission_decision: _PermissionDecision,
    collector,
) -> ToolMessage | None:
    """处理权限拒绝响应。"""
    if permission_decision.reject_message is None:
        return None

    log_event(
        logger,
        logging.WARNING,
        "tool_permission_rejected",
        code="tool_permission_rejected",
        step_id=f"tool-call-{tool_call_id}",
        status="blocked",
        data={
            "tool": name,
            "permission_level": permission_decision.permission_level,
        },
    )
    collector.record(
        node_type="skill_call",
        node_name=name,
        input_data=args,
        output_data={
            "status": "rejected",
            **_permission_trace_output(permission_decision),
        },
        duration_ms=0,
    )
    return ToolMessage(
        content=permission_decision.reject_message,
        tool_call_id=tool_call_id,
    )


async def _call_one(
    *,
    tc: dict,
    tool_map: dict,
    state: AgentState,
    farm_id: int,
    original_input: str,
    collector,
) -> ToolMessage:
    """执行单个 tool_call，保持原有权限、pending 和 trace 顺序。"""
    name = tc["name"]
    raw_args = _execution_args_for_call(name, tc["args"])
    # 权限判定必须使用已补齐的确定性 operation，否则“结工资”这类写意图会被误判为查询。
    args = _tool_pending_args._build_pending_execution_args(
        name, raw_args, farm_id, original_input
    )
    tool_call_id = tc["id"]
    log_event(
        logger,
        logging.INFO,
        "tool_call_started",
        step_id=f"tool-call-{tool_call_id}",
        status="started",
        data={
            "tool": name,
            "arg_keys": sorted(str(key) for key in args),
        },
    )
    start = _time.perf_counter()

    tool = _runtime_tool_for_call(name, args, tool_map)
    permission_decision = _permission_decision(tool, name, state, args)

    message = _disabled_tool_message(
        name=name,
        args=args,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if message is not None:
        return message

    message = _permission_reject_message(
        name=name,
        args=args,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if message is not None:
        return message

    message = _validation_error_message(
        tool=tool,
        name=name,
        args=args,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
    )
    if message is not None:
        return message

    message = _tool_pending._pending_action_message(
        state=state,
        name=name,
        args=args,
        farm_id=farm_id,
        original_input=original_input,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
        logger=logger,
    )
    if message is not None:
        return message

    return await _invoke_read_tool_message(
        tool=tool,
        name=name,
        args=args,
        tool_call_id=tool_call_id,
        permission_decision=permission_decision,
        collector=collector,
        start=start,
        logger=logger,
    )


async def _parallel_tool_node(state: AgentState) -> dict:
    """并行执行多个 tool_calls 的节点。写操作 Skill 拦截为 pending action。"""
    set_round_index(state.get("trace_round_index"))
    last = state["messages"][-1]
    if not isinstance(last, AIMessage) or not last.tool_calls:
        return {"messages": []}

    farm_id = state.get("farm_id")
    if not isinstance(farm_id, int) or farm_id <= 0:
        return {
            "messages": [
                ToolMessage(
                    content="工具调用失败：缺少可信农场上下文。",
                    tool_call_id=tc["id"],
                )
                for tc in last.tool_calls
            ]
        }
    farm_uid = state.get("farm_uid")
    tool_map = {
        t.name: t for t in get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
    }
    collector = get_collector()

    original_input = _latest_human_input(state)

    tool_calls = _tool_pending_args._collapse_all_labor_payment_tool_calls(
        last.tool_calls, original_input
    )
    plan_messages = _tool_pending._pending_plan_tool_message(
        state=state,
        farm_id=farm_id,
        original_input=original_input,
        tool_calls=tool_calls,
    )
    if plan_messages is not None:
        _record_pending_plan_trace(collector, original_input)
        return {"messages": plan_messages}

    if len(tool_calls) == 1:
        results = [
            await _call_one(
                tc=tool_calls[0],
                tool_map=tool_map,
                state=state,
                farm_id=farm_id,
                original_input=original_input,
                collector=collector,
            )
        ]
    else:
        log_event(
            logger,
            logging.INFO,
            "parallel_tool_batch_started",
            step_id=f"parallel-tool-batch-{len(tool_calls)}",
            status="started",
            data={
                "tool_calls": len(tool_calls),
                "tools": [str(tc["name"]) for tc in tool_calls],
            },
        )
        batch_start = _time.perf_counter()
        results = await asyncio.gather(
            *[
                _call_one(
                    tc=tc,
                    tool_map=tool_map,
                    state=state,
                    farm_id=farm_id,
                    original_input=original_input,
                    collector=collector,
                )
                for tc in tool_calls
            ]
        )
        batch_duration = int((_time.perf_counter() - batch_start) * 1000)
        collector.record(
            node_type="parallel_batch",
            node_name=f"parallel_{len(results)}_skills",
            output_data={
                "parallel_count": len(results),
                "skills": [{"name": tc["name"]} for tc in tool_calls],
            },
            duration_ms=batch_duration,
        )

    return {"messages": results}


__all__ = ["_parallel_tool_node"]
