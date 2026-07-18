"""纯 Python Agent ReAct loop 测试。"""

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.state import AgentState
from app.agent.runtime.loop import (
    AgentLoopMaxStepsExceeded,
    run_agent_loop,
    stream_agent_loop,
)

pytestmark = pytest.mark.no_db


def _tool_call_message() -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call-1",
                "name": "weather",
                "args": {"city": "苏州"},
            }
        ],
    )


def _base_state() -> AgentState:
    return {
        "messages": [HumanMessage(content="明天天气")],
        "farm_id": 1,
        "farm_uid": "farm-uid-1",
        "intent": "agent",
        "user_id": "user-1",
        "session_id": "session-1",
    }


@pytest.mark.asyncio
async def test_run_agent_loop_returns_after_llm_without_tool_call(monkeypatch) -> None:
    """LLM 没有 tool call 时直接结束，并追加消息而不是覆盖历史。"""
    llm_node = AsyncMock(
        return_value={
            "messages": [AIMessage(content="明天晴")],
            "trace_round_index": 3,
        }
    )
    tool_node = AsyncMock()
    monkeypatch.setattr("app.agent.runtime.loop._llm_node", llm_node)
    monkeypatch.setattr("app.agent.runtime.loop._parallel_tool_node", tool_node)

    result = await run_agent_loop(_base_state())

    assert [message.content for message in result["messages"]] == [
        "明天天气",
        "明天晴",
    ]
    assert result["trace_round_index"] == 3
    llm_node.assert_awaited_once()
    tool_node.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_agent_loop_executes_tools_then_returns_to_llm(monkeypatch) -> None:
    """有 tool call 时执行工具，再带着工具结果回到 LLM 生成最终回复。"""
    tool_result = ToolMessage(content="晴天 25 度", tool_call_id="call-1")
    llm_node = AsyncMock(
        side_effect=[
            {"messages": [_tool_call_message()]},
            {"messages": [AIMessage(content="明天苏州晴，25 度。")]},
        ]
    )
    tool_node = AsyncMock(return_value={"messages": [tool_result]})
    monkeypatch.setattr("app.agent.runtime.loop._llm_node", llm_node)
    monkeypatch.setattr("app.agent.runtime.loop._parallel_tool_node", tool_node)

    result = await run_agent_loop(_base_state())

    assert [type(message) for message in result["messages"]] == [
        HumanMessage,
        AIMessage,
        ToolMessage,
        AIMessage,
    ]
    assert result["messages"][-1].content == "明天苏州晴，25 度。"
    assert llm_node.await_count == 2
    tool_node.assert_awaited_once()
    tool_state = tool_node.await_args.args[0]
    assert tool_state["messages"][-1].tool_calls[0]["name"] == "weather"


@pytest.mark.asyncio
async def test_run_agent_loop_raises_custom_error_at_max_steps(monkeypatch) -> None:
    """超过 max_steps 时抛项目自定义异常。"""
    llm_node = AsyncMock(return_value={"messages": [_tool_call_message()]})
    tool_node = AsyncMock(
        return_value={
            "messages": [ToolMessage(content="晴天", tool_call_id="call-1")]
        }
    )
    monkeypatch.setattr("app.agent.runtime.loop._llm_node", llm_node)
    monkeypatch.setattr("app.agent.runtime.loop._parallel_tool_node", tool_node)

    with pytest.raises(AgentLoopMaxStepsExceeded, match="max_steps=1"):
        await run_agent_loop(_base_state(), max_steps=1)


@pytest.mark.asyncio
async def test_stream_agent_loop_yields_llm_and_tool_updates(monkeypatch) -> None:
    """事件流保持旧 updates 语义：每个节点产出的增量 messages 单独向外暴露。"""
    llm_node = AsyncMock(
        side_effect=[
            {"messages": [_tool_call_message()]},
            {"messages": [AIMessage(content="明天苏州晴，25 度。")]},
        ]
    )
    tool_node = AsyncMock(
        return_value={
            "messages": [ToolMessage(content="晴天 25 度", tool_call_id="call-1")]
        }
    )
    monkeypatch.setattr("app.agent.runtime.loop._llm_node", llm_node)
    monkeypatch.setattr("app.agent.runtime.loop._parallel_tool_node", tool_node)

    events = [event async for event in stream_agent_loop(_base_state())]

    assert list(events[0]) == ["llm"]
    assert list(events[1]) == ["tools"]
    assert list(events[2]) == ["llm"]
    assert events[2]["llm"]["messages"][0].content == "明天苏州晴，25 度。"
