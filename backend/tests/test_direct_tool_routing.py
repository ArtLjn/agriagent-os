"""确定性工具路由测试。"""

from unittest.mock import MagicMock, patch

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
