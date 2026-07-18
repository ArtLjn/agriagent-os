"""测试 _llm_node 双阶段模型选择 + 请求内重试循环。"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from app.context.models import ContextBundle


def _make_state(messages, farm_id=1):
    """构造 AgentState。"""
    return {"messages": messages, "farm_id": farm_id}


def _make_llm_mock(response_content="OK", tool_calls=None):
    """构造 mock LLM 实例。"""
    llm = AsyncMock()
    resp = MagicMock()
    resp.content = response_content
    resp.tool_calls = tool_calls or []
    resp.response_metadata = {}
    llm.ainvoke = AsyncMock(return_value=resp)
    llm.bind_tools = MagicMock(return_value=llm)
    llm.model_name = "test-model"
    return llm, resp


def test_filter_tool_calls_by_selected_drops_unbound_tool():
    """手动 JSON 工具调用只能执行本轮绑定的候选工具。"""
    from app.agent.runtime.direct_routing import filter_tool_calls_by_selected

    selected_tool = MagicMock()
    selected_tool.name = "create_crop_cycle"
    tool_calls = [
        {"name": "create_crop_template", "args": {"crop_name": "小麦"}, "id": "tc1"},
        {"name": "create_crop_cycle", "args": {"crop_name": "小麦"}, "id": "tc2"},
    ]

    result = filter_tool_calls_by_selected(tool_calls, [selected_tool])

    assert result == [
        {"name": "create_crop_cycle", "args": {"crop_name": "小麦"}, "id": "tc2"}
    ]


def test_detect_missed_tool_call_flags_write_success_claim_without_tool_call():
    """写操作被模型直接说已记录时，应视为漏调工具。"""
    from app.agent.runtime.messages import _detect_missed_tool_call

    selected_tool = MagicMock()
    selected_tool.name = "create_cost_record"

    should_retry, matched = _detect_missed_tool_call(
        "今天买橘子种子130张三赊账",
        "已记录：今天购买橘子种子，花费130元，由张三赊账。",
        [selected_tool],
    )

    assert should_retry is True
    assert matched == [selected_tool]


def test_detect_missed_tool_call_flags_polite_write_success_claim():
    """“已为您记录”这类礼貌成功话术也不能绕过写工具。"""
    from app.agent.runtime.messages import _detect_missed_tool_call

    selected_tool = MagicMock()
    selected_tool.name = "create_cost_record"

    should_retry, matched = _detect_missed_tool_call(
        "今天买橘子种子130张三赊账",
        (
            "已为您记录：向张三赊购橘子种子，金额 130 元。\n\n"
            "请问这笔费用应该计入哪个成本分类？"
        ),
        [selected_tool],
    )

    assert should_retry is True
    assert matched == [selected_tool]


def test_detect_missed_tool_call_flags_worker_create_success_claim():
    """新增工人成功话术没有 tool_call 时，也必须 fail closed。"""
    from app.agent.runtime.messages import _detect_missed_tool_call

    selected_tool = MagicMock()
    selected_tool.name = "manage_workers"

    should_retry, matched = _detect_missed_tool_call(
        "新来一个工人李丽工资100一天",
        "已新增工人李丽，日工资为100元。",
        [selected_tool],
    )

    assert should_retry is True
    assert matched == [selected_tool]


@pytest.mark.asyncio
@pytest.mark.no_db
@patch("app.agent.runtime.llm_invocation._record_llm_success")
@patch("app.agent.runtime.llm_invocation._record_llm_failure")
@patch("app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model")
@patch("app.agent.runtime.nodes.get_llm")
@patch("app.agent.runtime.nodes.get_langchain_tools")
@patch("app.agent.runtime.nodes._get_classifier", return_value=None)
@patch("app.agent.runtime.nodes.select_tools", return_value=[])
@patch(
    "app.agent.runtime.llm_prompt._get_farm_context",
    return_value={
        "display_name": "农友",
        "farm_location": "苏州",
        "farm_coords": "",
        "active_crops": "",
    },
)
@patch("app.agent.runtime.nodes.check_quota", return_value=True)
@patch("app.agent.runtime.nodes.increment_round", return_value=1)
@patch("app.agent.runtime.nodes.get_collector")
@patch("app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs)
@patch("app.agent.runtime.nodes._find_last_human_message", return_value="你有啥爱好")
@patch("app.agent.runtime.llm_prompt.get_request_date")
@patch("app.agent.runtime.llm_prompt._get_runtime_context_bundle")
@patch("app.agent.runtime.llm_prompt.get_composer")
@patch("app.agent.runtime.nodes.settings")
async def test_no_tool_chat_retries_json_tool_leak_as_natural_reply(
    mock_settings,
    mock_composer,
    mock_context_bundle,
    mock_date,
    mock_find_human,
    mock_sliding,
    mock_collector,
    mock_round,
    mock_quota,
    mock_farm_ctx,
    mock_select,
    mock_classifier,
    mock_tools,
    mock_get_llm,
    mock_circuit_key,
    mock_failure,
    mock_success,
):
    """no-tools 闲聊误吐工具 JSON 时，应内部重试为自然语言回复。"""
    mock_settings.ai = MagicMock(failover_max_retries=1, parallel_tool_calls=True)
    mock_composer.return_value.compose.side_effect = lambda scene, **_kwargs: (
        f"{scene} prompt"
    )
    mock_collector.return_value = MagicMock()
    mock_context_bundle.return_value = (
        ContextBundle(blocks=[], token_budget=1000, token_estimate=0),
        {
            "display_name": "农友",
            "farm_location": "苏州",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    mock_tools.return_value = []

    llm = AsyncMock()
    llm.model_name = "test-model"
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(
                content='{"name": "weather", "parameters": {"location": "苏州"}}',
                tool_calls=[],
            ),
            AIMessage(
                content="我喜欢把农场里的事理顺，也能陪你轻松聊几句。", tool_calls=[]
            ),
        ]
    )
    mock_get_llm.return_value = llm

    from app.agent.runtime.nodes import _llm_node

    result = await _llm_node(
        {"messages": [HumanMessage(content="你有啥爱好")], "farm_id": 1}
    )

    response = result["messages"][0]
    assert response.content == "我喜欢把农场里的事理顺，也能陪你轻松聊几句。"
    assert not response.tool_calls
    assert llm.ainvoke.await_count == 2
    first_prompt = llm.ainvoke.await_args_list[0].args[0][0].content
    retry_prompt = llm.ainvoke.await_args_list[1].args[0][0].content
    assert first_prompt.startswith("system_chat prompt")
    assert "不要输出工具名或 JSON" in retry_prompt


@pytest.mark.asyncio
@pytest.mark.no_db
@patch("app.agent.runtime.llm_invocation._record_llm_success")
@patch("app.agent.runtime.llm_invocation._record_llm_failure")
@patch("app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model")
@patch("app.agent.runtime.nodes.get_llm")
@patch("app.agent.runtime.nodes.get_langchain_tools")
@patch("app.agent.runtime.nodes._get_classifier", return_value=None)
@patch("app.agent.runtime.nodes.select_tools", return_value=[])
@patch(
    "app.agent.runtime.llm_prompt._get_farm_context",
    return_value={
        "display_name": "农友",
        "farm_location": "苏州",
        "farm_coords": "",
        "active_crops": "",
    },
)
@patch("app.agent.runtime.nodes.check_quota", return_value=True)
@patch("app.agent.runtime.nodes.increment_round", return_value=1)
@patch("app.agent.runtime.nodes.get_collector")
@patch("app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs)
@patch("app.agent.runtime.nodes._find_last_human_message", return_value="你喜欢啥")
@patch("app.agent.runtime.llm_prompt.get_request_date")
@patch("app.agent.runtime.llm_prompt._get_runtime_context_bundle")
@patch("app.agent.runtime.llm_prompt.get_composer")
@patch("app.agent.runtime.nodes.settings")
async def test_no_tool_chat_retry_still_leaks_uses_friendly_fallback(
    mock_settings,
    mock_composer,
    mock_context_bundle,
    mock_date,
    mock_find_human,
    mock_sliding,
    mock_collector,
    mock_round,
    mock_quota,
    mock_farm_ctx,
    mock_select,
    mock_classifier,
    mock_tools,
    mock_get_llm,
    mock_circuit_key,
    mock_failure,
    mock_success,
):
    """no-tools 重试仍泄漏工具 JSON 时，返回友好兜底而不是内部异常文案。"""
    mock_settings.ai = MagicMock(failover_max_retries=1, parallel_tool_calls=True)
    mock_composer.return_value.compose.side_effect = lambda scene, **_kwargs: (
        f"{scene} prompt"
    )
    mock_collector.return_value = MagicMock()
    mock_context_bundle.return_value = (
        ContextBundle(blocks=[], token_budget=1000, token_estimate=0),
        {
            "display_name": "农友",
            "farm_location": "苏州",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    mock_tools.return_value = []

    leaked = '{"name": "get_farm_status", "parameters": {}}'
    llm = AsyncMock()
    llm.model_name = "test-model"
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content=leaked, tool_calls=[]),
            AIMessage(content=leaked, tool_calls=[]),
        ]
    )
    mock_get_llm.return_value = llm

    from app.agent.runtime.nodes import _llm_node

    result = await _llm_node(
        {"messages": [HumanMessage(content="你喜欢啥")], "farm_id": 1}
    )

    response = result["messages"][0]
    assert "我刚才没组织好" in response.content
    assert "工具调用格式异常" not in response.content
    assert '"name"' not in response.content
    assert not response.tool_calls
    assert llm.ainvoke.await_count == 2


@pytest.mark.asyncio
@pytest.mark.no_db
@patch("app.agent.runtime.llm_invocation._record_llm_success")
@patch("app.agent.runtime.llm_invocation._record_llm_failure")
@patch("app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model")
@patch("app.agent.runtime.nodes.get_llm")
@patch("app.agent.runtime.nodes.get_langchain_tools")
@patch("app.agent.runtime.nodes._get_classifier", return_value=None)
@patch("app.agent.runtime.nodes.select_tools", return_value=["get_crop_cycle_info"])
@patch("app.agent.runtime.nodes.expand_by_chain", return_value={"get_crop_cycle_info"})
@patch(
    "app.agent.runtime.llm_prompt._get_farm_context",
    return_value={
        "display_name": "农友",
        "farm_location": "",
        "farm_coords": "",
        "active_crops": "",
    },
)
@patch("app.agent.runtime.nodes.check_quota", return_value=True)
@patch("app.agent.runtime.nodes.increment_round", return_value=1)
@patch("app.agent.runtime.nodes.get_collector")
@patch("app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs)
@patch(
    "app.agent.runtime.nodes._find_last_human_message",
    return_value="水稻茬口1号棚今天",
)
@patch("app.agent.runtime.llm_prompt.get_request_date")
@patch("app.agent.runtime.llm_prompt._get_runtime_context_bundle")
@patch("app.agent.runtime.llm_prompt.get_composer")
@patch("app.agent.runtime.nodes.settings")
async def test_operation_work_order_clarification_keeps_write_tool_bound(
    mock_settings,
    mock_composer,
    mock_context_bundle,
    mock_date,
    mock_find_human,
    mock_sliding,
    mock_collector,
    mock_round,
    mock_quota,
    mock_farm_ctx,
    mock_expand,
    mock_select,
    mock_classifier,
    mock_tools,
    mock_get_llm,
    mock_circuit_key,
    mock_failure,
    mock_success,
):
    """作业单追问后的补充句，不能只绑定读工具导致写工具 JSON 泄漏。"""
    mock_settings.ai = MagicMock(failover_max_retries=1, parallel_tool_calls=True)
    mock_composer.return_value.compose.return_value = "system prompt"
    mock_collector.return_value = MagicMock()
    mock_context_bundle.return_value = (
        ContextBundle(blocks=[], token_budget=1000, token_estimate=0),
        {
            "display_name": "农友",
            "farm_location": "",
            "farm_coords": "",
            "active_crops": "",
        },
    )

    read_tool = MagicMock()
    read_tool.name = "get_crop_cycle_info"
    write_tool = MagicMock()
    write_tool.name = "create_operation_work_order"
    mock_tools.return_value = [read_tool, write_tool]

    tool_call = {
        "name": "create_operation_work_order",
        "args": {
            "worker_name": "李丽",
            "crop_cycle_name": "水稻",
            "planting_unit_name": "1号棚",
            "work_date": "2026-06-08",
            "operation_type": "采收",
            "unit_price": 100,
        },
        "id": "tc_work_order",
    }
    llm = AsyncMock()
    llm.model_name = "test-model"
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="", tool_calls=[tool_call]))
    mock_get_llm.return_value = llm

    from app.agent.runtime.nodes import _llm_node

    result = await _llm_node(
        {
            "messages": [
                HumanMessage(content="安排李丽去水稻采收"),
                AIMessage(content="确认后我帮您创建农事作业单。"),
                HumanMessage(content="水稻茬口1号棚今天"),
            ],
            "farm_id": 1,
            "intent": "query",
        }
    )

    response = result["messages"][0]
    assert response.content == ""
    assert response.tool_calls[0]["name"] == "create_operation_work_order"
    assert response.tool_calls[0]["args"] == tool_call["args"]
    bound_tools = llm.bind_tools.call_args.args[0]
    assert {tool.name for tool in bound_tools} == {
        "get_crop_cycle_info",
        "create_operation_work_order",
    }


@pytest.mark.asyncio
@patch("app.agent.runtime.llm_invocation._record_llm_success")
@patch("app.agent.runtime.llm_invocation._record_llm_failure")
@patch("app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model")
@patch("app.agent.runtime.nodes.get_llm")
@patch("app.agent.runtime.nodes.get_langchain_tools")
@patch("app.agent.runtime.nodes._get_classifier", return_value=None)
@patch("app.agent.runtime.nodes.select_tools", return_value=["create_cost_record"])
@patch("app.agent.runtime.nodes.expand_by_chain", return_value={"create_cost_record"})
@patch(
    "app.agent.runtime.llm_prompt._get_farm_context",
    return_value={
        "display_name": "农友",
        "farm_location": "",
        "farm_coords": "",
        "active_crops": "",
    },
)
@patch("app.agent.runtime.nodes.check_quota", return_value=True)
@patch("app.agent.runtime.nodes.increment_round", return_value=1)
@patch("app.agent.runtime.nodes.get_collector")
@patch("app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs)
@patch(
    "app.agent.runtime.nodes._find_last_human_message",
    return_value="今天买橘子种子130张三赊账",
)
@patch("app.agent.runtime.llm_prompt.get_request_date")
@patch("app.agent.runtime.llm_prompt._get_runtime_context_bundle")
@patch("app.agent.runtime.llm_prompt.get_composer")
@patch("app.agent.runtime.nodes.settings")
async def test_write_success_claim_retry_accepts_native_tool_calls(
    mock_settings,
    mock_composer,
    mock_context_bundle,
    mock_date,
    mock_find_human,
    mock_sliding,
    mock_collector,
    mock_round,
    mock_quota,
    mock_farm_ctx,
    mock_expand,
    mock_select,
    mock_classifier,
    mock_tools,
    mock_get_llm,
    mock_circuit_key,
    mock_failure,
    mock_success,
):
    """模型先说已记录、重试后返回原生 tool_calls 时，应进入工具调用流程。"""
    mock_settings.ai = MagicMock(failover_max_retries=1, parallel_tool_calls=True)
    mock_composer.return_value.compose.return_value = "system prompt"
    mock_collector.return_value = MagicMock()
    mock_context_bundle.return_value = (
        ContextBundle(blocks=[], token_budget=1000, token_estimate=0),
        {
            "display_name": "农友",
            "farm_location": "",
            "farm_coords": "",
            "active_crops": "",
        },
    )

    tool_mock = MagicMock()
    tool_mock.name = "create_cost_record"
    mock_tools.return_value = [tool_mock]

    first_response = AIMessage(
        content="已记录：今天购买橘子种子，花费130元，由张三赊账。",
        tool_calls=[],
    )
    retry_response = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "create_cost_record",
                "args": {
                    "amount": 130,
                    "category": "种子",
                    "record_type": "cost",
                    "record_subtype": "赊账",
                    "counterparty": "张三",
                },
                "id": "tc_retry",
            }
        ],
    )
    llm = AsyncMock()
    llm.model_name = "test-model"
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first_response, retry_response])
    mock_get_llm.return_value = llm

    from app.agent.runtime.nodes import _llm_node

    result = await _llm_node(
        {"messages": [HumanMessage(content="今天买橘子种子130张三赊账")], "farm_id": 1}
    )

    response = result["messages"][0]
    assert response.content == ""
    assert response.tool_calls == retry_response.tool_calls


@pytest.mark.asyncio
@patch("app.agent.runtime.llm_invocation._record_llm_success")
@patch("app.agent.runtime.llm_invocation._record_llm_failure")
@patch("app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model")
@patch("app.agent.runtime.nodes.get_llm")
@patch("app.agent.runtime.nodes.get_langchain_tools")
@patch("app.agent.runtime.nodes._get_classifier", return_value=None)
@patch("app.agent.runtime.nodes.select_tools", return_value=["create_cost_record"])
@patch("app.agent.runtime.nodes.expand_by_chain", return_value={"create_cost_record"})
@patch(
    "app.agent.runtime.llm_prompt._get_farm_context",
    return_value={
        "display_name": "农友",
        "farm_location": "",
        "farm_coords": "",
        "active_crops": "",
    },
)
@patch("app.agent.runtime.nodes.check_quota", return_value=True)
@patch("app.agent.runtime.nodes.increment_round", return_value=1)
@patch("app.agent.runtime.nodes.get_collector")
@patch("app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs)
@patch(
    "app.agent.runtime.nodes._find_last_human_message",
    return_value="今天买橘子种子130张三赊账",
)
@patch("app.agent.runtime.llm_prompt.get_request_date")
@patch("app.agent.runtime.llm_prompt._get_runtime_context_bundle")
@patch("app.agent.runtime.llm_prompt.get_composer")
@patch("app.agent.runtime.nodes.settings")
async def test_write_success_claim_retry_fails_closed_without_tool_call(
    mock_settings,
    mock_composer,
    mock_context_bundle,
    mock_date,
    mock_find_human,
    mock_sliding,
    mock_collector,
    mock_round,
    mock_quota,
    mock_farm_ctx,
    mock_expand,
    mock_select,
    mock_classifier,
    mock_tools,
    mock_get_llm,
    mock_circuit_key,
    mock_failure,
    mock_success,
):
    """写操作重试仍无 tool_call 时，不能返回模型的已记录幻觉。"""
    mock_settings.ai = MagicMock(failover_max_retries=1, parallel_tool_calls=True)
    mock_composer.return_value.compose.return_value = "system prompt"
    mock_collector.return_value = MagicMock()
    mock_context_bundle.return_value = (
        ContextBundle(blocks=[], token_budget=1000, token_estimate=0),
        {
            "display_name": "农友",
            "farm_location": "",
            "farm_coords": "",
            "active_crops": "",
        },
    )

    tool_mock = MagicMock()
    tool_mock.name = "create_cost_record"
    mock_tools.return_value = [tool_mock]

    first_response = AIMessage(
        content="已记录：今天购买橘子种子，花费130元，由张三赊账。",
        tool_calls=[],
    )
    retry_response = AIMessage(
        content="已记录：今天购买橘子种子，花费130元，由张三赊账。",
        tool_calls=[],
    )
    llm = AsyncMock()
    llm.model_name = "test-model"
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(side_effect=[first_response, retry_response])
    mock_get_llm.return_value = llm

    from app.agent.runtime.nodes import _llm_node

    result = await _llm_node(
        {"messages": [HumanMessage(content="今天买橘子种子130张三赊账")], "farm_id": 1}
    )

    response = result["messages"][0]
    assert "已记录" not in response.content
    assert "还没有执行" in response.content
    assert not response.tool_calls


@pytest.mark.asyncio
@patch("app.agent.runtime.llm_invocation._record_llm_success")
@patch("app.agent.runtime.llm_invocation._record_llm_failure")
@patch("app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model")
@patch("app.agent.runtime.nodes.get_llm")
@patch("app.agent.runtime.nodes.get_langchain_tools")
@patch("app.agent.runtime.nodes._get_classifier", return_value=None)
@patch("app.agent.runtime.nodes.select_tools", return_value=["create_cost_record"])
@patch("app.agent.runtime.nodes.expand_by_chain", return_value={"create_cost_record"})
@patch(
    "app.agent.runtime.llm_prompt._get_farm_context",
    return_value={
        "display_name": "农友",
        "farm_location": "",
        "farm_coords": "",
        "active_crops": "",
    },
)
@patch("app.agent.runtime.nodes.check_quota", return_value=True)
@patch("app.agent.runtime.nodes.increment_round", return_value=1)
@patch("app.agent.runtime.nodes.get_collector")
@patch("app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs)
@patch(
    "app.agent.runtime.nodes._find_last_human_message",
    return_value="今天买橘子种子130张三赊账",
)
@patch("app.agent.runtime.llm_prompt.get_request_date")
@patch("app.agent.runtime.llm_prompt._get_runtime_context_bundle")
@patch("app.agent.runtime.llm_prompt.get_composer")
@patch("app.agent.runtime.nodes.settings")
async def test_polite_write_success_claim_with_clarification_fails_closed(
    mock_settings,
    mock_composer,
    mock_context_bundle,
    mock_date,
    mock_find_human,
    mock_sliding,
    mock_collector,
    mock_round,
    mock_quota,
    mock_farm_ctx,
    mock_expand,
    mock_select,
    mock_classifier,
    mock_tools,
    mock_get_llm,
    mock_circuit_key,
    mock_failure,
    mock_success,
):
    """一边说已为您记录一边追问分类，也不能返回未执行成功话术。"""
    mock_settings.ai = MagicMock(failover_max_retries=1, parallel_tool_calls=True)
    mock_composer.return_value.compose.return_value = "system prompt"
    mock_collector.return_value = MagicMock()
    mock_context_bundle.return_value = (
        ContextBundle(blocks=[], token_budget=1000, token_estimate=0),
        {
            "display_name": "农友",
            "farm_location": "",
            "farm_coords": "",
            "active_crops": "",
        },
    )

    tool_mock = MagicMock()
    tool_mock.name = "create_cost_record"
    mock_tools.return_value = [tool_mock]

    hallucinated_reply = (
        "已为您记录：向张三赊购橘子种子，金额 130 元。\n\n"
        "请问这笔费用应该计入哪个成本分类？（例如：种子费、农资等）"
    )
    llm = AsyncMock()
    llm.model_name = "test-model"
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content=hallucinated_reply, tool_calls=[]),
            AIMessage(content=hallucinated_reply, tool_calls=[]),
        ]
    )
    mock_get_llm.return_value = llm

    from app.agent.runtime.nodes import _llm_node

    result = await _llm_node(
        {"messages": [HumanMessage(content="今天买橘子种子130张三赊账")], "farm_id": 1}
    )

    response = result["messages"][0]
    assert "已为您记录" not in response.content
    assert "还没有执行" in response.content
    assert "确认" in response.content


@pytest.mark.asyncio
@patch("app.agent.runtime.llm_invocation._record_llm_success")
@patch("app.agent.runtime.llm_invocation._record_llm_failure")
@patch("app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model")
@patch("app.agent.runtime.nodes.get_llm")
@patch("app.agent.runtime.nodes.get_langchain_tools")
@patch("app.agent.runtime.nodes._get_classifier", return_value=None)
@patch("app.agent.runtime.nodes.select_tools", return_value=["create_cost_record"])
@patch("app.agent.runtime.nodes.expand_by_chain", return_value={"create_cost_record"})
@patch(
    "app.agent.runtime.llm_prompt._get_farm_context",
    return_value={
        "display_name": "农友",
        "farm_location": "",
        "farm_coords": "",
        "active_crops": "",
    },
)
@patch("app.agent.runtime.nodes.check_quota", return_value=True)
@patch("app.agent.runtime.nodes.increment_round", return_value=1)
@patch("app.agent.runtime.nodes.get_collector")
@patch("app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs)
@patch(
    "app.agent.runtime.nodes._find_last_human_message",
    return_value="买了200块化肥",
)
@patch("app.agent.runtime.llm_prompt.get_request_date")
@patch("app.agent.runtime.llm_prompt._get_runtime_context_bundle")
@patch("app.agent.runtime.llm_prompt.get_composer")
@patch("app.agent.runtime.nodes.settings")
async def test_empty_write_response_fails_closed_without_retry_tool_call(
    mock_settings,
    mock_composer,
    mock_context_bundle,
    mock_date,
    mock_find_human,
    mock_sliding,
    mock_collector,
    mock_round,
    mock_quota,
    mock_farm_ctx,
    mock_expand,
    mock_select,
    mock_classifier,
    mock_tools,
    mock_get_llm,
    mock_circuit_key,
    mock_failure,
    mock_success,
):
    """写意图下模型空回复不能返回“换个说法”，必须明确未执行。"""
    mock_settings.ai = MagicMock(failover_max_retries=1, parallel_tool_calls=True)
    mock_composer.return_value.compose.return_value = "system prompt"
    mock_collector.return_value = MagicMock()
    mock_context_bundle.return_value = (
        ContextBundle(blocks=[], token_budget=1000, token_estimate=0),
        {
            "display_name": "农友",
            "farm_location": "",
            "farm_coords": "",
            "active_crops": "",
        },
    )

    tool_mock = MagicMock()
    tool_mock.name = "create_cost_record"
    mock_tools.return_value = [tool_mock]

    llm = AsyncMock()
    llm.model_name = "test-model"
    llm.bind_tools = MagicMock(return_value=llm)
    llm.ainvoke = AsyncMock(
        side_effect=[
            AIMessage(content="", tool_calls=[]),
            AIMessage(content="", tool_calls=[]),
        ]
    )
    mock_get_llm.return_value = llm

    from app.agent.runtime.nodes import _llm_node

    result = await _llm_node(
        {"messages": [HumanMessage(content="买了200块化肥")], "farm_id": 1}
    )

    response = result["messages"][0]
    assert "换个说法" not in response.content
    assert "还没有执行" in response.content
    assert "待确认" in response.content
    assert llm.ainvoke.await_count == 2


@pytest.fixture(autouse=True)
def _reset_singletons():
    """每个测试前后重置全局单例。"""
    import app.core.llm_client_manager as mgr_module

    mgr_module._manager = None
    yield
    mgr_module._manager = None


class TestDualPhaseModelSelection:
    """测试双阶段模型：无 tool 结果用 tool-selection，有 tool 结果用 generation。"""

    @pytest.mark.asyncio
    @patch("app.agent.runtime.llm_invocation._record_llm_success")
    @patch("app.agent.runtime.llm_invocation._record_llm_failure")
    @patch(
        "app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model"
    )
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=["web_search"])
    @patch("app.agent.runtime.nodes.expand_by_chain", return_value={"web_search"})
    @patch(
        "app.agent.runtime.llm_prompt._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.llm_prompt.get_request_date")
    @patch("app.agent.runtime.llm_prompt._get_season", return_value="春季")
    @patch("app.agent.runtime.llm_prompt.get_composer")
    def test_no_tool_results_uses_generation_role(
        self,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_expand,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """默认 agent intent 无 ToolMessage 时使用 generation 角色。"""
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm, resp = _make_llm_mock()
        mock_get_llm.return_value = llm

        from app.agent.runtime.nodes import _llm_node

        state = _make_state([HumanMessage(content="你好")])
        asyncio.get_event_loop().run_until_complete(_llm_node(state))

        mock_get_llm.assert_called_once_with(role="generation")

    @pytest.mark.asyncio
    @patch("app.agent.runtime.llm_invocation._record_llm_success")
    @patch("app.agent.runtime.llm_invocation._record_llm_failure")
    @patch(
        "app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model"
    )
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=["web_search"])
    @patch("app.agent.runtime.nodes.expand_by_chain", return_value={"web_search"})
    @patch(
        "app.agent.runtime.llm_prompt._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="天气如何")
    @patch("app.agent.runtime.llm_prompt.get_request_date")
    @patch("app.agent.runtime.llm_prompt._get_season", return_value="春季")
    @patch("app.agent.runtime.llm_prompt.get_composer")
    def test_with_tool_results_uses_generation_role(
        self,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_expand,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """有 ToolMessage 时，get_llm 应以 role='generation' 调用。"""
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm, resp = _make_llm_mock()
        mock_get_llm.return_value = llm

        from app.agent.runtime.nodes import _llm_node

        tool_msg = ToolMessage(content="晴，25度", tool_call_id="tc1")
        state = _make_state(
            [
                HumanMessage(content="天气如何"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "get_weather", "id": "tc1", "args": {}}],
                ),
                tool_msg,
            ]
        )
        asyncio.get_event_loop().run_until_complete(_llm_node(state))

        mock_get_llm.assert_called_once_with(role="generation")


class TestRetryLoop:
    """测试请求内重试循环。"""

    @pytest.mark.asyncio
    @patch("app.agent.runtime.llm_invocation._record_llm_success")
    @patch("app.agent.runtime.llm_invocation._record_llm_failure")
    @patch(
        "app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model"
    )
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.llm_prompt._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.llm_prompt.get_request_date")
    @patch("app.agent.runtime.llm_prompt._get_season", return_value="春季")
    @patch("app.agent.runtime.llm_prompt.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_successful_llm_call_logs_completion(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
        caplog,
    ):
        """LLM 成功调用后应输出可见的完成日志。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm, resp = _make_llm_mock(response_content="你好")
        mock_get_llm.return_value = llm

        from app.agent.runtime.nodes import _llm_node

        with caplog.at_level("INFO", logger="app.agent.runtime.nodes"):
            state = _make_state([HumanMessage(content="你好")])
            asyncio.get_event_loop().run_until_complete(_llm_node(state))

        assert "LLM 调用完成" in caplog.text
        assert "key=test/model" in caplog.text
        assert "model=test-model" in caplog.text

    @pytest.mark.asyncio
    @patch("app.agent.runtime.llm_invocation._record_llm_success")
    @patch("app.agent.runtime.llm_invocation._record_llm_failure")
    @patch(
        "app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model"
    )
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=["web_search"])
    @patch("app.agent.runtime.nodes.expand_by_chain", return_value={"web_search"})
    @patch(
        "app.agent.runtime.llm_prompt._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.llm_prompt.get_request_date")
    @patch("app.agent.runtime.llm_prompt._get_season", return_value="春季")
    @patch("app.agent.runtime.llm_prompt.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_success_on_first_attempt_no_retry(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_expand,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """第一次成功时不触发重试。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm, resp = _make_llm_mock()
        mock_get_llm.return_value = llm

        from app.agent.runtime.nodes import _llm_node

        state = _make_state([HumanMessage(content="你好")])
        asyncio.get_event_loop().run_until_complete(_llm_node(state))

        assert mock_get_llm.call_count == 1
        mock_success.assert_called_once_with("test/model")
        mock_failure.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.agent.runtime.llm_invocation._record_llm_success")
    @patch("app.agent.runtime.llm_invocation._record_llm_failure")
    @patch(
        "app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model"
    )
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.llm_prompt._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.llm_prompt.get_request_date")
    @patch("app.agent.runtime.llm_prompt._get_season", return_value="春季")
    @patch("app.agent.runtime.llm_prompt.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_provider_error_triggers_retry(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """PROVIDER 级错误（如 ConnectionError）应触发重试。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        call_count = 0

        def make_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            llm = AsyncMock()
            llm.model_name = f"model-{call_count}"
            llm.bind_tools = MagicMock(return_value=llm)

            if call_count == 1:
                # 第一次调用失败（PROVIDER 级错误）
                llm.ainvoke = AsyncMock(side_effect=ConnectionError("连接失败"))
            else:
                # 第二次调用成功
                resp = MagicMock()
                resp.content = "重试成功"
                resp.tool_calls = []
                resp.response_metadata = {}
                llm.ainvoke = AsyncMock(return_value=resp)

            return llm

        mock_get_llm.side_effect = make_llm

        # classify_error 对 ConnectionError 返回 PROVIDER
        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error",
            return_value=ErrorLevel.PROVIDER,
        ):
            from app.agent.runtime.nodes import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            asyncio.get_event_loop().run_until_complete(_llm_node(state))

        # 第一次失败 + 第二次重试成功
        assert call_count == 2
        mock_failure.assert_called_once()
        mock_success.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.agent.runtime.llm_invocation._record_llm_success")
    @patch("app.agent.runtime.llm_invocation._record_llm_failure")
    @patch(
        "app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model"
    )
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.llm_prompt._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.llm_prompt.get_request_date")
    @patch("app.agent.runtime.llm_prompt._get_season", return_value="春季")
    @patch("app.agent.runtime.llm_prompt.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_model_error_no_retry(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """MODEL 级错误（如 400 schema 错误）不重试，直接抛出。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm = AsyncMock()
        llm.model_name = "test-model"
        llm.bind_tools = MagicMock(return_value=llm)
        llm.ainvoke = AsyncMock(side_effect=RuntimeError("400 schema error"))
        mock_get_llm.return_value = llm

        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error", return_value=ErrorLevel.MODEL
        ):
            from app.agent.runtime.nodes import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            with pytest.raises(RuntimeError, match="400 schema error"):
                asyncio.get_event_loop().run_until_complete(_llm_node(state))

        # MODEL 级错误不重试，get_llm 只调用一次
        assert mock_get_llm.call_count == 1
        mock_failure.assert_called_once()
        mock_success.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.agent.runtime.llm_invocation._record_llm_success")
    @patch("app.agent.runtime.llm_invocation._record_llm_failure")
    @patch(
        "app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model"
    )
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.llm_prompt._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.llm_prompt.get_request_date")
    @patch("app.agent.runtime.llm_prompt._get_season", return_value="春季")
    @patch("app.agent.runtime.llm_prompt.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_all_retries_exhausted_raises(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """所有重试用尽后，最后一次异常抛出。"""
        mock_settings.ai = MagicMock(failover_max_retries=2, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        call_count = 0

        def make_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            llm = AsyncMock()
            llm.model_name = f"model-{call_count}"
            llm.bind_tools = MagicMock(return_value=llm)
            llm.ainvoke = AsyncMock(side_effect=ConnectionError("持续连接失败"))
            return llm

        mock_get_llm.side_effect = make_llm

        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error",
            return_value=ErrorLevel.PROVIDER,
        ):
            from app.agent.runtime.nodes import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            with pytest.raises(ConnectionError, match="持续连接失败"):
                asyncio.get_event_loop().run_until_complete(_llm_node(state))

        # failover_max_retries=2，调用 2 次
        assert call_count == 2
        assert mock_failure.call_count == 2
        mock_success.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.agent.runtime.llm_invocation._record_llm_success")
    @patch("app.agent.runtime.llm_invocation._record_llm_failure")
    @patch(
        "app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model"
    )
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=["web_search"])
    @patch("app.agent.runtime.nodes.expand_by_chain", return_value={"web_search"})
    @patch(
        "app.agent.runtime.llm_prompt._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.llm_prompt.get_request_date")
    @patch("app.agent.runtime.llm_prompt._get_season", return_value="春季")
    @patch("app.agent.runtime.llm_prompt.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_retry_rebinds_tools(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_expand,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """重试时应重新调用 bind_tools 绑定选中的工具。"""
        mock_settings.ai = MagicMock(failover_max_retries=3, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()

        tool_mock = MagicMock()
        tool_mock.name = "web_search"
        mock_tools.return_value = [tool_mock]

        call_count = 0

        def make_llm(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            llm = AsyncMock()
            llm.model_name = f"model-{call_count}"
            llm.bind_tools = MagicMock(return_value=llm)

            if call_count == 1:
                llm.ainvoke = AsyncMock(side_effect=ConnectionError("连接失败"))
            else:
                resp = MagicMock()
                resp.content = "成功"
                resp.tool_calls = []
                resp.response_metadata = {}
                llm.ainvoke = AsyncMock(return_value=resp)

            return llm

        mock_get_llm.side_effect = make_llm

        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error",
            return_value=ErrorLevel.PROVIDER,
        ):
            from app.agent.runtime.nodes import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            asyncio.get_event_loop().run_until_complete(_llm_node(state))

        # 两次调用都应 bind_tools
        assert call_count == 2


class TestRetryWithSingleAttempt:
    """测试 failover_max_retries=1 时退化为无重试行为。"""

    @pytest.mark.asyncio
    @patch("app.agent.runtime.llm_invocation._record_llm_success")
    @patch("app.agent.runtime.llm_invocation._record_llm_failure")
    @patch(
        "app.agent.runtime.llm_invocation._build_circuit_key", return_value="test/model"
    )
    @patch("app.agent.runtime.nodes.get_llm")
    @patch("app.agent.runtime.nodes.get_langchain_tools")
    @patch("app.agent.runtime.nodes._get_classifier", return_value=None)
    @patch("app.agent.runtime.nodes.select_tools", return_value=[])
    @patch(
        "app.agent.runtime.llm_prompt._get_farm_context",
        return_value={
            "farm_location": "睢宁",
            "display_name": "农友",
            "farm_coords": "",
            "active_crops": "",
        },
    )
    @patch("app.agent.runtime.nodes.check_quota", return_value=True)
    @patch("app.agent.runtime.nodes.increment_round", return_value=1)
    @patch("app.agent.runtime.nodes.get_collector")
    @patch(
        "app.agent.runtime.nodes.sliding_window_compact", side_effect=lambda msgs: msgs
    )
    @patch("app.agent.runtime.nodes._find_last_human_message", return_value="你好")
    @patch("app.agent.runtime.llm_prompt.get_request_date")
    @patch("app.agent.runtime.llm_prompt._get_season", return_value="春季")
    @patch("app.agent.runtime.llm_prompt.get_composer")
    @patch("app.agent.runtime.nodes.settings")
    def test_single_attempt_no_retry_on_failure(
        self,
        mock_settings,
        mock_composer,
        mock_season,
        mock_date,
        mock_find_human,
        mock_sliding,
        mock_collector,
        mock_round,
        mock_quota,
        mock_farm_ctx,
        mock_select,
        mock_classifier,
        mock_tools,
        mock_get_llm,
        mock_circuit_key,
        mock_failure,
        mock_success,
    ):
        """failover_max_retries=1 时失败直接抛出，不重试。"""
        mock_settings.ai = MagicMock(failover_max_retries=1, parallel_tool_calls=True)
        mock_composer.return_value.compose.return_value = "system prompt"
        mock_collector.return_value = MagicMock()
        mock_tools.return_value = []

        llm = AsyncMock()
        llm.model_name = "test-model"
        llm.bind_tools = MagicMock(return_value=llm)
        llm.ainvoke = AsyncMock(side_effect=ConnectionError("连接失败"))
        mock_get_llm.return_value = llm

        from app.core.llm_client_manager import ErrorLevel

        with patch(
            "app.core.llm_client_manager.classify_error",
            return_value=ErrorLevel.PROVIDER,
        ):
            from app.agent.runtime.nodes import _llm_node

            state = _make_state([HumanMessage(content="你好")])
            with pytest.raises(ConnectionError):
                asyncio.get_event_loop().run_until_complete(_llm_node(state))

        assert mock_get_llm.call_count == 1
