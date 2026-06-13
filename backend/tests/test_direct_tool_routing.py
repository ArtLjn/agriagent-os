"""确定性工具路由测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def _make_tool(name: str):
    tool = MagicMock()
    tool.name = name
    return tool


@pytest.mark.asyncio
async def test_strong_read_tool_match_skips_initial_llm_call():
    """强规则命中的读工具应直接进入 tool_node，不先让 LLM 猜工具。"""
    from app.agent.graph import _llm_node

    with (
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            return_value={
                "farm_location": "睢宁",
                "display_name": "农友",
                "farm_coords": "",
                "active_crops": "",
            },
        ),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[_make_tool("get_weather_forecast")],
        ),
        patch(
            "app.agent.runtime.nodes.select_tools",
            return_value=["get_weather_forecast"],
        ),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes._get_classifier") as mock_classifier,
        patch("app.agent.runtime.nodes.get_llm") as mock_get_llm,
    ):
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="今天天气")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls == [
        {
            "name": "get_weather_forecast",
            "args": {},
            "id": "direct_get_weather_forecast",
            "type": "tool_call",
        }
    ]
    mock_get_llm.assert_not_called()
    mock_classifier.assert_not_called()


@pytest.mark.asyncio
async def test_cost_summary_query_skips_tool_selection_llm_call():
    """账单/余额查询可以确定性调用 Skill，避免 LLM 漏查真实数据。"""
    from app.agent.graph import _llm_node

    with (
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            return_value={
                "farm_location": "睢宁",
                "display_name": "农友",
                "farm_coords": "",
                "active_crops": "",
            },
        ),
        patch("app.agent.runtime.nodes.get_composer"),
        patch("app.agent.runtime.nodes.get_collector", return_value=MagicMock()),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[_make_tool("get_cost_summary")],
        ),
        patch(
            "app.agent.runtime.nodes.select_tools",
            return_value=["get_cost_summary"],
        ),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes._get_classifier") as mock_classifier,
        patch("app.agent.runtime.nodes.get_llm") as mock_get_llm,
    ):
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="我的余额")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls == [
        {
            "name": "get_cost_summary",
            "args": {},
            "id": "direct_get_cost_summary",
            "type": "tool_call",
        }
    ]
    mock_get_llm.assert_not_called()
    mock_classifier.assert_not_called()


@pytest.mark.asyncio
async def test_daily_operation_advice_skips_initial_llm_call():
    """每日农事建议应直接查天气和农场状态，避免模型泄漏 JSON 工具调用。"""
    from app.agent.graph import _llm_node

    with (
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            return_value={
                "farm_location": "睢宁",
                "display_name": "农友",
                "farm_coords": "",
                "active_crops": "",
            },
        ),
        patch("app.agent.runtime.nodes.get_collector", return_value=MagicMock()),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[
                _make_tool("get_weather_forecast"),
                _make_tool("get_farm_status"),
            ],
        ),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes._get_classifier") as mock_classifier,
        patch("app.agent.runtime.nodes.get_llm") as mock_get_llm,
    ):
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="今天适合做什么")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls == [
        {
            "name": "get_weather_forecast",
            "args": {},
            "id": "direct_get_weather_forecast",
            "type": "tool_call",
        },
        {
            "name": "get_farm_status",
            "args": {},
            "id": "direct_get_farm_status",
            "type": "tool_call",
        },
    ]
    mock_get_llm.assert_not_called()
    mock_classifier.assert_not_called()


@pytest.mark.asyncio
async def test_debt_summary_query_skips_tool_selection_llm_call():
    """总欠款查询可以确定性调用 Skill，避免 LLM 只回答人工欠款。"""
    from app.agent.graph import _llm_node

    with (
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            return_value={
                "farm_location": "睢宁",
                "display_name": "农友",
                "farm_coords": "",
                "active_crops": "",
            },
        ),
        patch("app.agent.runtime.nodes.get_composer"),
        patch("app.agent.runtime.nodes.get_collector", return_value=MagicMock()),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[_make_tool("get_debt_summary")],
        ),
        patch(
            "app.agent.runtime.nodes.select_tools",
            return_value=["get_debt_summary"],
        ),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes._get_classifier") as mock_classifier,
        patch("app.agent.runtime.nodes.get_llm") as mock_get_llm,
    ):
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="我欠别人多少钱")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls == [
        {
            "name": "get_debt_summary",
            "args": {"scope": "total_payable"},
            "id": "direct_get_debt_summary",
            "type": "tool_call",
        }
    ]
    mock_get_llm.assert_not_called()
    mock_classifier.assert_not_called()


@pytest.mark.asyncio
async def test_total_payable_query_passes_scope_to_direct_debt_summary():
    """问总欠款时直达 get_debt_summary 必须带 total_payable scope。"""
    from app.agent.graph import _llm_node

    with (
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            return_value={
                "farm_location": "睢宁",
                "display_name": "农友",
                "farm_coords": "",
                "active_crops": "",
            },
        ),
        patch("app.agent.runtime.nodes.get_composer"),
        patch("app.agent.runtime.nodes.get_collector", return_value=MagicMock()),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[_make_tool("get_debt_summary")],
        ),
        patch(
            "app.agent.runtime.nodes.select_tools",
            return_value=["get_debt_summary"],
        ),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes._get_classifier") as mock_classifier,
        patch("app.agent.runtime.nodes.get_llm") as mock_get_llm,
    ):
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="我还欠多少钱")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls == [
        {
            "name": "get_debt_summary",
            "args": {"scope": "total_payable"},
            "id": "direct_get_debt_summary",
            "type": "tool_call",
        }
    ]
    mock_get_llm.assert_not_called()
    mock_classifier.assert_not_called()


@pytest.mark.asyncio
async def test_explicit_debt_query_keeps_empty_direct_args():
    """明确说赊账时只查普通赊账，不混入人工欠薪。"""
    from app.agent.graph import _llm_node

    with (
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            return_value={
                "farm_location": "睢宁",
                "display_name": "农友",
                "farm_coords": "",
                "active_crops": "",
            },
        ),
        patch("app.agent.runtime.nodes.get_composer"),
        patch("app.agent.runtime.nodes.get_collector", return_value=MagicMock()),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[_make_tool("get_debt_summary")],
        ),
        patch(
            "app.agent.runtime.nodes.select_tools",
            return_value=["get_debt_summary"],
        ),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes._get_classifier") as mock_classifier,
        patch("app.agent.runtime.nodes.get_llm") as mock_get_llm,
    ):
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="老王那边赊账还欠多少")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls == [
        {
            "name": "get_debt_summary",
            "args": {},
            "id": "direct_get_debt_summary",
            "type": "tool_call",
        }
    ]
    mock_get_llm.assert_not_called()
    mock_classifier.assert_not_called()


@pytest.mark.asyncio
async def test_workers_query_skips_initial_llm_call():
    """工人列表查询应确定性调用 get_workers，避免 LLM 漏查或空工具调用。"""
    from app.agent.graph import _llm_node

    with (
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            return_value={
                "farm_location": "睢宁",
                "display_name": "农友",
                "farm_coords": "",
                "active_crops": "",
            },
        ),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[_make_tool("get_workers")],
        ),
        patch(
            "app.agent.runtime.nodes.select_tools",
            return_value=["get_workers"],
        ),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes._get_classifier") as mock_classifier,
        patch("app.agent.runtime.nodes.get_llm") as mock_get_llm,
    ):
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="我的工人")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls == [
        {
            "name": "get_workers",
            "args": {},
            "id": "direct_get_workers",
            "type": "tool_call",
        }
    ]
    mock_get_llm.assert_not_called()
    mock_classifier.assert_not_called()


@pytest.mark.asyncio
async def test_generic_crop_cycle_query_routes_to_cycle_list_without_llm():
    """泛问“我的茬口”时应查询茬口列表，而不是农场状态摘要。"""
    from app.agent.graph import _llm_node

    with (
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            return_value={
                "farm_location": "睢宁",
                "display_name": "农友",
                "farm_coords": "",
                "active_crops": "",
            },
        ),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[
                _make_tool("get_crop_cycles"),
                _make_tool("get_crop_cycle_info"),
                _make_tool("get_farm_status"),
            ],
        ),
        patch(
            "app.agent.runtime.nodes.select_tools",
            return_value=["get_crop_cycles", "get_crop_cycle_info", "get_farm_status"],
        ),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes._get_classifier") as mock_classifier,
        patch("app.agent.runtime.nodes.get_llm") as mock_get_llm,
    ):
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="我的茬口")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    message = result["messages"][0]
    assert isinstance(message, AIMessage)
    assert message.tool_calls == [
        {
            "name": "get_crop_cycles",
            "args": {},
            "id": "direct_get_crop_cycles",
            "type": "tool_call",
        }
    ]
    mock_get_llm.assert_not_called()
    mock_classifier.assert_not_called()


@pytest.mark.asyncio
async def test_specific_crop_cycle_query_with_id_does_not_fold_to_farm_status():
    """明确给出茬口 ID 时，不应把详情查询折叠成整体状态。"""
    from app.agent.graph import _llm_node

    llm = MagicMock()
    llm.model_name = "test-model"
    llm.bind_tools.return_value = llm
    llm.ainvoke = AsyncMock(
        return_value=AIMessage(
            content="需要调用 3 号茬口详情",
            response_metadata={"token_usage": {"total_tokens": 1}},
        )
    )

    with (
        patch(
            "app.agent.runtime.nodes._get_runtime_context_bundle",
            return_value=(
                MagicMock(blocks=[], render_text=lambda: ""),
                {
                    "farm_location": "睢宁",
                    "display_name": "农友",
                    "farm_coords": "",
                    "active_crops": "",
                },
            ),
        ),
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            return_value={
                "farm_location": "睢宁",
                "display_name": "农友",
                "farm_coords": "",
                "active_crops": "",
            },
        ),
        patch("app.agent.runtime.nodes.get_composer") as mock_get_composer,
        patch("app.agent.runtime.nodes.get_collector", return_value=MagicMock()),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[
                _make_tool("get_crop_cycle_info"),
                _make_tool("get_farm_status"),
            ],
        ),
        patch(
            "app.agent.runtime.nodes.select_tools",
            return_value=["get_crop_cycle_info", "get_farm_status"],
        ),
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes._get_classifier", return_value=None),
        patch("app.agent.runtime.nodes.get_llm", return_value=llm) as mock_get_llm,
    ):
        mock_get_composer.return_value.compose.return_value = "system prompt"
        await _llm_node(
            {
                "messages": [HumanMessage(content="看一下3号茬口")],
                "farm_id": 1,
                "intent": "query",
            }
        )

    mock_get_llm.assert_called_once()
    llm.bind_tools.assert_called_once()
