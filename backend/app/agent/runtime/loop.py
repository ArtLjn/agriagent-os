"""纯 Python ReAct 运行循环。"""

from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage

from app.agent.runtime.nodes import _llm_node
from app.agent.runtime.support import AgentRuntimeError
from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.state import AgentState


class AgentLoopMaxStepsExceeded(AgentRuntimeError):
    """Agent loop 超过最大步数。"""


def _merge_state_update(state: AgentState, update: dict) -> AgentState:
    """合并节点增量，显式保留历史消息追加语义。"""
    merged = dict(state)
    for key, value in update.items():
        if key == "messages":
            merged["messages"] = [*state.get("messages", []), *value]
        else:
            merged[key] = value
    return merged


def _has_tool_calls(state: AgentState) -> bool:
    last = state["messages"][-1]
    return isinstance(last, AIMessage) and bool(last.tool_calls)


async def run_agent_loop(state: AgentState, max_steps: int = 15) -> AgentState:
    """运行 ReAct loop，直到 LLM 直接回复或达到最大步数。"""
    current = dict(state)
    for _step in range(max_steps):
        llm_update = await _llm_node(current)
        current = _merge_state_update(current, llm_update)
        if not _has_tool_calls(current):
            return current

        tool_update = await _parallel_tool_node(current)
        current = _merge_state_update(current, tool_update)

    raise AgentLoopMaxStepsExceeded(f"Agent loop exceeded max_steps={max_steps}")


async def stream_agent_loop(
    state: AgentState,
    max_steps: int = 15,
) -> AsyncGenerator[dict[str, dict], None]:
    """按节点增量流式运行 ReAct loop，保持旧 updates 事件形态。"""
    current = dict(state)
    for _step in range(max_steps):
        llm_update = await _llm_node(current)
        current = _merge_state_update(current, llm_update)
        yield {"llm": llm_update}
        if not _has_tool_calls(current):
            return

        tool_update = await _parallel_tool_node(current)
        current = _merge_state_update(current, tool_update)
        yield {"tools": tool_update}

    raise AgentLoopMaxStepsExceeded(f"Agent loop exceeded max_steps={max_steps}")


__all__ = ["AgentLoopMaxStepsExceeded", "run_agent_loop", "stream_agent_loop"]
