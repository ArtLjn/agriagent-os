"""工具选择瘦身后的 runtime 路由契约。"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.runtime.direct_routing import (
    can_return_direct_tool_messages,
    filter_tool_calls_by_selected,
)


pytestmark = pytest.mark.no_db


def _make_tool(name: str):
    tool = MagicMock()
    tool.name = name
    return tool


class _FakeLLM:
    model_name = "fake-model"

    def __init__(self) -> None:
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools: list, **_kwargs):
        self.bound_tool_names = [tool.name for tool in tools]
        return self

    async def ainvoke(self, _messages):
        return AIMessage(content="交给模型选择工具", tool_calls=[])


def _runtime_patches(fake_llm: _FakeLLM, tools: list):
    return [
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes.get_langchain_tools", return_value=tools),
        patch("app.agent.runtime.nodes.get_llm", return_value=fake_llm),
        patch("app.agent.runtime.nodes._build_circuit_key", return_value="fake/model"),
        patch("app.agent.runtime.nodes._record_llm_success"),
        patch("app.agent.runtime.nodes._record_llm_failure"),
        patch(
            "app.agent.runtime.nodes._get_runtime_context_bundle",
            new=AsyncMock(
                return_value=(
                    MagicMock(blocks=[], render_text=lambda: ""),
                    {
                        "farm_location": "睢宁",
                        "display_name": "农友",
                        "farm_coords": "",
                        "active_crops": "",
                    },
                )
            ),
        ),
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            new=AsyncMock(
                return_value={
                    "farm_location": "睢宁",
                    "display_name": "农友",
                    "farm_coords": "",
                    "active_crops": "",
                }
            ),
        ),
        patch("app.agent.runtime.nodes.get_prompt_cache"),
        patch("app.agent.runtime.nodes.get_composer"),
        patch("app.agent.runtime.nodes.get_collector", return_value=MagicMock()),
        patch(
            "app.agent.runtime.nodes.sliding_window_compact",
            side_effect=lambda messages: messages,
        ),
        patch("app.agent.runtime.nodes._warm_tool_caches", new_callable=AsyncMock),
        patch("app.agent.runtime.nodes.settings"),
    ]


def _enter_runtime_patches(stack: ExitStack, fake_llm: _FakeLLM, tools: list):
    entered = [
        stack.enter_context(patcher) for patcher in _runtime_patches(fake_llm, tools)
    ]
    prompt_cache = entered[8]
    prompt_cache.return_value.get.return_value = "系统提示"
    settings = entered[-1]
    settings.ai.parallel_tool_calls = False
    settings.ai.failover_max_retries = 1


@pytest.mark.asyncio
async def test_query_request_enters_llm_with_read_tools():
    """普通 query 请求不再跳过 LLM，而是绑定只读候选工具。"""
    from app.agent.graph import _llm_node

    fake_llm = _FakeLLM()
    tools = [
        _make_tool("get_weather_forecast"),
        _make_tool("get_farm_status"),
        _make_tool("create_operation_work_order"),
    ]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="今天天气对作物有什么影响")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    assert isinstance(result["messages"][0], AIMessage)
    assert fake_llm.bound_tool_names == [
        "get_weather_forecast",
        "get_farm_status",
    ]


def test_filter_tool_calls_by_selected_drops_unbound_tools():
    """工具执行前仍按本轮绑定白名单过滤模型输出。"""
    selected_tools = [_make_tool("get_farm_status")]
    tool_calls = [
        {"name": "get_farm_status", "args": {}, "id": "ok"},
        {"name": "create_operation_work_order", "args": {}, "id": "blocked"},
    ]

    assert filter_tool_calls_by_selected(tool_calls, selected_tools) == [
        {"name": "get_farm_status", "args": {}, "id": "ok"}
    ]


def test_direct_tool_messages_can_still_return_without_final_llm():
    """已存在的 direct tool result 仍可直返最终结果。"""
    messages = [
        ToolMessage(
            content="【工人列表】\n- 老王",
            tool_call_id="direct_get_workers",
        )
    ]

    assert can_return_direct_tool_messages(messages) is True


def test_direct_manage_cost_query_result_can_return_without_final_llm():
    """manage_cost 的查询类直返沿用工具名白名单，operation 由上游路由保证。"""
    messages = [
        ToolMessage(
            content="您目前总欠款为 630.00 元，构成如下：\n- 普通赊账：230.00 元",
            tool_call_id="call-manage-cost",
            name="manage_cost",
            additional_kwargs={"operation": "query_debt"},
        )
    ]

    assert can_return_direct_tool_messages(messages) is True


def test_direct_manage_cost_summary_result_goes_through_final_llm():
    """manage_cost 非欠款查询 operation 仍需最终 LLM 组织表达。"""
    messages = [
        ToolMessage(
            content="收支汇总：\n  总成本：100.00 元",
            tool_call_id="call-manage-cost",
            name="manage_cost",
            additional_kwargs={"operation": "query_summary"},
        )
    ]

    assert can_return_direct_tool_messages(messages) is False


def test_legacy_debt_summary_direct_name_is_not_allowed():
    """旧 get_debt_summary 目录已退役，直返白名单不能继续接受旧工具名。"""
    messages = [
        ToolMessage(
            content="您目前总欠款为 630.00 元",
            tool_call_id="direct_get_debt_summary",
        )
    ]

    assert can_return_direct_tool_messages(messages) is False


def test_weather_tool_message_should_go_through_final_llm():
    """天气 Skill 原始结果需要最终 LLM 组织语言。"""
    messages = [
        ToolMessage(
            content="城市: 苏州\n未来天数: 3天\n7/10: 天气☀️, 最高35℃",
            tool_call_id="call-random",
            name="get_weather_forecast",
        )
    ]

    assert can_return_direct_tool_messages(messages) is False
