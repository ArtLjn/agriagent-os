"""Final Agent 上下文隔离与输出防泄漏回归测试。"""

import logging
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from app.agent.router import RouterDecision
from app.agent.runtime.nodes import _llm_node
from app.context.core.models import ContextBundle

pytestmark = pytest.mark.no_db


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeLLM:
    model_name = "fake-final-model"

    def __init__(self) -> None:
        self.bound_tool_calls: list[dict] = []
        self.invocations: list[list] = []
        self.responses: list[AIMessage] = [AIMessage(content="结果是 20。")]

    def bind_tools(self, tools: list, **kwargs):
        self.bound_tool_calls.append(
            {"tools": [tool.name for tool in tools], "kwargs": dict(kwargs)}
        )
        return self

    async def ainvoke(self, messages: list):
        self.invocations.append(messages)
        if self.responses and isinstance(self.responses[0], Exception):
            raise self.responses.pop(0)
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0]


def _eda446a0_messages() -> list:
    return [
        HumanMessage(content="30 除以 1.5 等于多少？"),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "id": "call-calc",
                    "name": "calculate_arithmetic",
                    "args": {"expression": "30 / 1.5"},
                }
            ],
        ),
        ToolMessage(
            content='{"expression":"30 / 1.5","result":20,"unit":""}',
            name="calculate_arithmetic",
            tool_call_id="call-calc",
            status="success",
        ),
    ]


def _farm_context() -> dict:
    return {
        "display_name": "农友",
        "farm_location": "睢宁",
        "farm_coords": "",
        "active_crops": "",
    }


async def _empty_context_bundle(**_kwargs):
    return ContextBundle(blocks=[], token_budget=0, token_estimate=0), _farm_context()


def _runtime_patches(fake_llm: _FakeLLM, collector: MagicMock):
    return [
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch(
            "app.agent.runtime.nodes.get_langchain_tools",
            return_value=[_FakeTool("calculate_arithmetic")],
        ),
        patch("app.agent.runtime.nodes.get_llm", return_value=fake_llm),
        patch(
            "app.agent.runtime.llm_invocation._build_circuit_key",
            return_value="fake/model",
        ),
        patch("app.agent.runtime.llm_invocation._record_llm_success"),
        patch("app.agent.runtime.llm_invocation._record_llm_failure"),
        patch(
            "app.agent.runtime.llm_prompt._get_runtime_context_bundle",
            new=AsyncMock(side_effect=_empty_context_bundle),
        ),
        patch(
            "app.agent.runtime.llm_prompt._get_farm_context",
            new=AsyncMock(return_value=_farm_context()),
        ),
        patch("app.agent.runtime.llm_prompt.get_prompt_cache"),
        patch("app.agent.runtime.llm_prompt.get_composer"),
        patch("app.agent.runtime.nodes.get_collector", return_value=collector),
        patch(
            "app.agent.runtime.nodes.sliding_window_compact",
            side_effect=lambda messages: messages,
        ),
        patch(
            "app.agent.runtime.llm_node_steps._warm_tool_caches", new_callable=AsyncMock
        ),
        patch("app.agent.runtime.nodes.settings"),
    ]


def _enter_runtime_patches(
    stack: ExitStack, fake_llm: _FakeLLM, collector: MagicMock
) -> list[MagicMock]:
    entered = [
        stack.enter_context(patcher)
        for patcher in _runtime_patches(fake_llm, collector)
    ]
    prompt_cache = entered[8]
    prompt_cache.return_value.get.return_value = "系统提示"
    settings = entered[-1]
    settings.ai.parallel_tool_calls = False
    settings.ai.failover_max_retries = 1
    return entered


def test_final_context_builder_drops_raw_tool_history_and_records_trace() -> None:
    from app.agent.runtime.final_response import FinalContextBuilder

    collector = MagicMock()
    request = FinalContextBuilder().build(
        state={
            "messages": _eda446a0_messages(),
            "farm_id": 1,
            "farm_uid": "farm-uid-1",
            "intent": "agent",
            "user_id": "user-1",
            "session_id": "session-eda446a0",
        },
        system_text="系统提示",
        context_bundle=ContextBundle(blocks=[], token_budget=0, token_estimate=0),
        collector=collector,
    )

    system, messages = request.to_llm_input()
    assert isinstance(system, SystemMessage)
    assert all(isinstance(message, HumanMessage) for message in messages)
    assert not any(isinstance(message, ToolMessage) for message in messages)
    assert request.trace_metadata["dropped_tool_call_history"] is True
    assert request.tool_results[0].tool_name == "calculate_arithmetic"
    assert "20" in request.tool_results[0].facts[0]

    rendered = "\n".join([str(system.content), *[str(m.content) for m in messages]])
    assert "tool_calls" not in rendered
    assert "ToolMessage" not in rendered
    assert "30 / 1.5" in rendered

    trace_call = collector.record.call_args.kwargs
    assert trace_call["node_type"] == "final_context"
    assert trace_call["node_name"] == "build"
    assert trace_call["output_data"]["source_message_count"] == 3
    assert trace_call["output_data"]["final_message_count"] == 1
    assert trace_call["output_data"]["tool_result_count"] == 1
    assert trace_call["output_data"]["dropped_tool_call_history"] is True


def test_final_context_builder_emits_single_line_audit_log(caplog) -> None:
    from app.agent.runtime.final_response import FinalContextBuilder

    with caplog.at_level(logging.INFO, logger="app.agent.audit"):
        FinalContextBuilder().build(
            state={
                "messages": _eda446a0_messages(),
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-eda446a0",
            },
            system_text="系统提示",
            context_bundle=ContextBundle(blocks=[], token_budget=0, token_estimate=0),
        )

    assert "event=agent_audit" in caplog.text
    assert "phase=final_response" in caplog.text
    assert "boundary=FINAL_NO_TOOLS" in caplog.text
    assert "sop=final_context_valid" in caplog.text
    assert "tool_results=1" in caplog.text


@pytest.mark.asyncio
async def test_final_llm_invocation_uses_clean_messages_and_tool_choice_none() -> None:
    fake_llm = _FakeLLM()
    collector = MagicMock()
    captured: dict = {}

    async def _capture_invoke(**kwargs):
        captured.update(kwargs)
        return (
            AIMessage(content="结果是 20。"),
            kwargs["raw_llm"],
            kwargs["llm"],
            "fake/model",
            1,
            "fake-final-model",
        )

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, collector)
        stack.enter_context(
            patch(
                "app.agent.runtime.llm_node_steps._invoke_llm_with_retry",
                new=AsyncMock(side_effect=_capture_invoke),
            )
        )
        await _llm_node(
            {
                "messages": _eda446a0_messages(),
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-eda446a0",
                "router_decision": RouterDecision(
                    selected_tools=["calculate_arithmetic"],
                    tool_choice="auto",
                ),
            }
        )

    assert captured["selected_tools"] == []
    assert captured["tool_choice"] == "none"
    assert fake_llm.bound_tool_calls == [
        {"tools": [], "kwargs": {"tool_choice": "none"}}
    ]
    assert all(isinstance(message, HumanMessage) for message in captured["messages"])
    assert not any(isinstance(message, ToolMessage) for message in captured["messages"])
    assert "tool_calls" not in str(captured["messages"])


def test_output_guard_detects_final_response_leak_types() -> None:
    from app.agent.runtime.final_response import check_final_output_leak

    native = check_final_output_leak(
        AIMessage(
            content="",
            tool_calls=[{"id": "call-1", "name": "calculate_arithmetic", "args": {}}],
        )
    )
    content_json = check_final_output_leak(
        AIMessage(content='{"name":"calculate_arithmetic","arguments":{"x":1}}')
    )
    protocol = check_final_output_leak(AIMessage(content="tool_calls 已准备好。"))
    raw_json = check_final_output_leak(AIMessage(content='{"answer":"结果是 20"}'))
    raw_json_list = check_final_output_leak(
        AIMessage(content='[{"answer":"结果是 20"}]')
    )
    embedded_json = check_final_output_leak(
        AIMessage(content='结果如下：{"answer":"20"}')
    )
    embedded_json_list = check_final_output_leak(
        AIMessage(content='结果如下：[{"answer":"20"}]')
    )
    no_need_tool = check_final_output_leak(
        AIMessage(content="结果是 20，不需要调用工具。")
    )
    no_need_tool_variant = check_final_output_leak(
        AIMessage(content="结果是 20，无需再调用工具。")
    )

    assert native.leak_type == "native_tool_calls"
    assert content_json.leak_type == "content_tool_call_json"
    assert protocol.leak_type == "protocol_keyword"
    assert raw_json.leak_type == "raw_json_object"
    assert raw_json_list.leak_type == "raw_json_output"
    assert embedded_json.leak_type == "raw_json_object"
    assert embedded_json_list.leak_type == "raw_json_output"
    assert no_need_tool.leak_type == "protocol_keyword"
    assert no_need_tool_variant.leak_type == "protocol_keyword"


@pytest.mark.parametrize(
    ("tool_message", "expected_status"),
    [
        (
            ToolMessage(content="工具调用失败: timeout", tool_call_id="call-failed"),
            "error",
        ),
        (
            ToolMessage(
                content="参数校验失败: 缺少 expression",
                tool_call_id="call-validation",
                status="error",
            ),
            "error",
        ),
    ],
)
def test_fail_closed_uses_no_reliable_result_for_failed_tool_messages(
    tool_message: ToolMessage,
    expected_status: str,
) -> None:
    from app.agent.runtime.final_response import (
        FinalContextBuilder,
        fail_closed_final_response,
    )

    request = FinalContextBuilder().build(
        state={
            "messages": [
                HumanMessage(content="帮我算一下"),
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": str(tool_message.tool_call_id),
                            "name": "calculate_arithmetic",
                            "args": {},
                        }
                    ],
                ),
                tool_message,
            ],
            "farm_id": 1,
            "farm_uid": "farm-uid-1",
            "intent": "agent",
            "user_id": "user-1",
            "session_id": "session-failed-tool",
        },
        system_text="系统提示",
        context_bundle=ContextBundle(blocks=[], token_budget=0, token_estimate=0),
    )

    final_text = fail_closed_final_response(request)
    assert request.tool_results[0].status == expected_status
    assert "没有可靠结果可展示" in final_text
    assert "已拿到工具结果" not in final_text


@pytest.mark.asyncio
async def test_eda446a0_regression_fail_closed_keeps_tool_result_context() -> None:
    fake_llm = _FakeLLM()
    fake_llm.responses = [
        AIMessage(content='{"name":"calculate_arithmetic","arguments":{"x":1}}'),
        AIMessage(content="需要先调用工具获取真实数据，请稍后重试。"),
    ]
    collector = MagicMock()

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, collector)
        result = await _llm_node(
            {
                "messages": _eda446a0_messages(),
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-eda446a0",
                "router_decision": RouterDecision(
                    selected_tools=["calculate_arithmetic"],
                    tool_choice="auto",
                ),
            }
        )

    final_text = result["messages"][0].content
    assert "需要先调用工具" not in final_text
    assert "已拿到工具结果" in final_text
    assert "tool_calls" not in final_text
    assert "arguments" not in final_text

    guard_nodes = [
        call.kwargs
        for call in collector.record.call_args_list
        if call.kwargs.get("node_type") == "output_guard"
    ]
    assert guard_nodes
    assert guard_nodes[-1]["node_name"] == "final_json_leak_check"
    assert guard_nodes[-1]["output_data"]["passed"] is False
    assert guard_nodes[-1]["output_data"]["retry_count"] == 1


@pytest.mark.asyncio
async def test_final_guard_retry_exception_fail_closed_keeps_reliable_tool_result() -> (
    None
):
    from app.agent.runtime.final_response import (
        FinalContextBuilder,
        guard_final_response,
    )

    fake_llm = _FakeLLM()
    fake_llm.responses = [RuntimeError("retry unavailable")]
    collector = MagicMock()
    request = FinalContextBuilder().build(
        state={
            "messages": _eda446a0_messages(),
            "farm_id": 1,
            "farm_uid": "farm-uid-1",
            "intent": "agent",
            "user_id": "user-1",
            "session_id": "session-eda446a0",
        },
        system_text="系统提示",
        context_bundle=ContextBundle(blocks=[], token_budget=0, token_estimate=0),
    )

    guarded = await guard_final_response(
        response=AIMessage(content='{"answer":"结果是 20"}'),
        llm=fake_llm,
        request=request,
        collector=collector,
    )

    assert "已拿到工具结果" in guarded.content
    assert guarded.response_metadata["output_guard"]["action"] == "fail_closed"
    assert guarded.response_metadata["final_response"]["boundary"] == "final_response"
    guard_trace = collector.record.call_args.kwargs
    assert guard_trace["node_name"] == "final_json_leak_check"
    assert guard_trace["output_data"]["action"] == "fail_closed"
    assert guard_trace["output_data"]["retry_count"] == 1


@pytest.mark.asyncio
async def test_final_guard_blocks_no_need_tool_phrase_before_reflection() -> None:
    fake_llm = _FakeLLM()
    fake_llm.responses = [
        AIMessage(content="结果是 20，不需要调用工具。"),
        AIMessage(content="需要先调用工具获取真实数据，请稍后重试。"),
    ]
    collector = MagicMock()

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, collector)
        result = await _llm_node(
            {
                "messages": _eda446a0_messages(),
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-eda446a0",
                "router_decision": RouterDecision(
                    selected_tools=["calculate_arithmetic"],
                    tool_choice="auto",
                ),
            }
        )

    final_text = result["messages"][0].content
    assert "不需要调用工具" not in final_text
    assert "需要先调用工具" not in final_text
    assert "已拿到工具结果" in final_text


@pytest.mark.asyncio
async def test_final_reply_data_source_uses_final_context_tool_results() -> None:
    fake_llm = _FakeLLM()
    collector = MagicMock()

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, collector)
        await _llm_node(
            {
                "messages": _eda446a0_messages(),
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-eda446a0",
                "router_decision": RouterDecision(
                    selected_tools=["calculate_arithmetic"],
                    tool_choice="auto",
                ),
            }
        )

    data_source_nodes = [
        call.kwargs
        for call in collector.record.call_args_list
        if call.kwargs.get("node_name") == "final_reply_data_source"
    ]
    assert data_source_nodes
    assert data_source_nodes[-1]["input_data"]["has_tool_results"] is True
    assert data_source_nodes[-1]["output_data"]["data_source"] == (
        "tool:calculate_arithmetic"
    )


def test_final_context_builder_limits_nested_json_fact_preview() -> None:
    from app.agent.runtime.final_response import FinalContextBuilder

    nested_items = [{"index": index, "value": "x" * 20} for index in range(80)]
    request = FinalContextBuilder().build(
        state={
            "messages": [
                HumanMessage(content="展示列表摘要"),
                ToolMessage(
                    content='{"result":'
                    + str(nested_items).replace("'", '"')
                    + ',"status":"ok"}',
                    name="large_result_tool",
                    tool_call_id="call-large",
                    status="success",
                ),
            ],
        },
        system_text="系统提示",
        context_bundle=ContextBundle(blocks=[], token_budget=0, token_estimate=0),
    )

    assert request.tool_results[0].facts
    assert all(len(fact) <= 180 for fact in request.tool_results[0].facts)
