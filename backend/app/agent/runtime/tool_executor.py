"""Agent Runtime 工具执行。"""

import asyncio
import logging
import time as _time

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.skills import get_langchain_tools
from app.agent.state import AgentState
from app.infra.pending_actions import (
    PENDING_MARKER,
    build_confirm_message,
    is_write_skill,
    store_pending,
)
from app.infra.trace_collector import get_collector

logger = logging.getLogger(__name__)


async def _parallel_tool_node(state: AgentState) -> dict:
    """并行执行多个 tool_calls 的节点。写操作 Skill 拦截为 pending action。"""
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

    # 获取用户原始输入（最近一条 HumanMessage）
    original_input = ""
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            original_input = msg.content[:200]
            break

    async def _call_one(tc: dict) -> ToolMessage:
        name = tc["name"]
        args = tc["args"]
        tool_call_id = tc["id"]
        logger.info("Skill 调用 %s(%s)", name, args)
        start = _time.perf_counter()

        tool = tool_map.get(name)

        # Pydantic 参数校验：在写操作拦截前校验，校验失败反馈 LLM 自纠错
        if tool and hasattr(tool, "args_schema") and tool.args_schema:
            try:
                tool.args_schema.model_validate(args)
            except Exception as e:
                error_msg = f"参数校验失败: {e}"
                logger.warning("Tool 参数校验失败 | name=%s | error=%s", name, e)
                return ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call_id,
                )

        # 写操作 Skill 拦截：存储 pending action，不直接执行
        if is_write_skill(name):
            action_id = store_pending(
                farm_id, name, args, original_input=original_input
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
                input_data=args,
                output_data="已拦截为 pending action",
                duration_ms=0,
            )
            confirm_text = build_confirm_message(
                name, args, original_input=original_input
            )
            return ToolMessage(
                content=f"{PENDING_MARKER} {confirm_text}",
                tool_call_id=tool_call_id,
            )

        # 读操作执行
        if not tool:
            return ToolMessage(content=f"未知工具: {name}", tool_call_id=tool_call_id)
        try:
            result = await tool.ainvoke(args)
            duration_ms = int((_time.perf_counter() - start) * 1000)
            summary = str(result)[:120].replace("\n", " ")
            logger.info(
                "Skill 完成 | name=%s | duration_ms=%d | result=%s",
                name,
                duration_ms,
                summary,
            )
            trace_output = getattr(result, "trace_data", None)
            if not trace_output:
                trace_output = {
                    "status": "success",
                    "reply_preview": str(result)[:500],
                }
            else:
                trace_output["reply_preview"] = str(result)[:500]
            collector.record(
                node_type="skill_call",
                node_name=name,
                input_data=args,
                output_data=trace_output,
                duration_ms=duration_ms,
            )
            return ToolMessage(content=str(result), tool_call_id=tool_call_id)
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

    if len(last.tool_calls) == 1:
        results = [await _call_one(last.tool_calls[0])]
    else:
        logger.info("并行执行 %d 个 Skill", len(last.tool_calls))
        batch_start = _time.perf_counter()
        results = await asyncio.gather(*[_call_one(tc) for tc in last.tool_calls])
        batch_duration = int((_time.perf_counter() - batch_start) * 1000)
        collector.record(
            node_type="parallel_batch",
            node_name=f"parallel_{len(results)}_skills",
            output_data={
                "parallel_count": len(results),
                "skills": [{"name": tc["name"]} for tc in last.tool_calls],
            },
            duration_ms=batch_duration,
        )

    return {"messages": results}


__all__ = ["_parallel_tool_node"]
