"""纯 Python ReAct 运行循环。

链路位置: 整条 /chat/stream 链路的最底层。

    stream_chat_events
        → stream_advisor           (application/advice/advisor.py)
            → stream_agent_loop    ← 本模块（流式版）
                ↻  _llm_node ⇄ _parallel_tool_node   ReAct 循环

两个孪生实现::

    run_agent_loop      一次性返回最终 state；同步路径与测试使用
    stream_agent_loop   每个 node 增量 yield；SSE 链路使用

循环终止条件:
    ① LLM 这一轮没有要求调用工具 → 视为给出最终回复，return
    ② 步数达到 max_steps          → raise AgentLoopMaxStepsExceeded

ReAct 模式: Reasoning + Acting
    LLM 决策（Reasoning） → 工具执行（Acting） → 结果回到 LLM → 再决策 …
"""

from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage

from app.agent.runtime.nodes import _llm_node
from app.agent.runtime.support import AgentLoopMaxStepsExceeded
from app.agent.runtime.tool_executor import _parallel_tool_node
from app.agent.state import AgentState


def _merge_state_update(state: AgentState, update: dict) -> AgentState:
    """合并节点增量，显式保留历史消息追加语义。

    ``messages`` 字段做追加合并（旧消息不能丢，LLM 需要完整上下文）；
    其他字段（如 ``intent``、``trace_round_index``）做覆盖合并。
    """
    merged = dict(state)
    for key, value in update.items():
        if key == "messages":
            merged["messages"] = [*state.get("messages", []), *value]
        else:
            merged[key] = value
    return merged


def _has_tool_calls(state: AgentState) -> bool:
    """判断 LLM 最新一条消息是否还想调工具 —— 不调则视为给出最终回复。"""
    last = state["messages"][-1]
    return isinstance(last, AIMessage) and bool(last.tool_calls)


async def run_agent_loop(state: AgentState, max_steps: int = 15) -> AgentState:
    """运行 ReAct loop，直到 LLM 直接回复或达到最大步数。

    用于同步路径（``invoke_advisor``）和测试场景，需要一次性拿到完整 state
    做断言时用它。SSE 链路请使用 ``stream_agent_loop``。
    """
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
    """按节点增量流式运行 ReAct loop，保持旧 updates 事件形态。

    与 ``run_agent_loop`` 的唯一区别: 每跑完一个 node 就 yield 一次，
    让上层（``stream_advisor``）能逐节点拿到增量做日志和最终回复提取。

    每次 yield 的结构::

        {"llm":   <llm_node 的 state 增量>}    含 AIMessage（带 tool_calls 或最终回复）
        {"tools": <tool_node 的 state 增量>}   含若干 ToolMessage（工具结果）
    """
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
