"""Skill Router trace 数据测试。"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.router import IntentFrame, RouterDecision
from app.agent.runtime import node_helpers as _node_helpers
from app.agent.runtime.nodes import _llm_node, _resolve_router_decision
from app.context.core.models import ContextBundle

pytestmark = pytest.mark.no_db


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeLLM:
    model_name = "fake-model"

    def bind_tools(self, _tools: list, **_kwargs):
        return self

    async def ainvoke(self, _messages):
        return AIMessage(content="已处理", tool_calls=[])


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
            return_value=[_FakeTool("get_farm_status")],
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
) -> None:
    entered = [
        stack.enter_context(patcher)
        for patcher in _runtime_patches(fake_llm, collector)
    ]
    prompt_cache = entered[8]
    prompt_cache.return_value.get.return_value = "系统提示"
    settings = entered[-1]
    settings.ai.parallel_tool_calls = False
    settings.ai.failover_max_retries = 1


def test_router_decision_trace_payload_includes_diagnostics() -> None:
    decision = RouterDecision(
        frames=[
            IntentFrame(
                domain="planting",
                intent="query_active_crops",
                risk="read",
                capability="manage_crop_cycle",
                operation="query_cycles",
                candidate_tools=["get_farm_status"],
                confidence=0.86,
                evidence={
                    "domain_scores": {"crop": 0.9},
                    "capability_scores": {"manage_crop_cycle": 0.88},
                    "operation_scores": {"query_cycles": 0.87},
                },
            )
        ],
        selected_tools=["get_farm_status"],
        selected_operations={"manage_crop_cycle": ["query_cycles"]},
        rejected_tools=["create_crop_cycle"],
        rejected_candidates=[
            {
                "name": "create_crop_cycle",
                "reason": "read_intent_write_operation",
            }
        ],
        policy_violations=["write_tool_blocked"],
        fallback_reason="test_reason",
        scores={
            "domain": {"crop": 0.9},
            "capability": {"manage_crop_cycle": 0.88},
            "operation": {"query_cycles": 0.87},
        },
        evidence={"selected_candidates": [{"name": "get_farm_status"}]},
    )

    payload = decision.to_trace_payload()

    assert payload["frames"][0]["intent"] == "query_active_crops"
    assert payload["selected_tools"] == ["get_farm_status"]
    assert payload["selected_operations"] == {"manage_crop_cycle": ["query_cycles"]}
    assert payload["rejected_tools"] == ["create_crop_cycle"]
    assert payload["rejected_candidates"][0]["reason"] == (
        "read_intent_write_operation"
    )
    assert payload["policy_violations"] == ["write_tool_blocked"]
    assert payload["fallback_reason"] == "test_reason"
    assert payload["scores"]["domain"] == {"crop": 0.9}
    assert payload["scores"]["capability"] == {"manage_crop_cycle": 0.88}
    assert payload["scores"]["operation"] == {"query_cycles": 0.87}
    assert payload["evidence"]["selected_candidates"] == [{"name": "get_farm_status"}]


def test_runtime_router_decision_returns_measured_duration() -> None:
    decision = RouterDecision(selected_tools=["get_farm_status"])

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "app.agent.runtime.nodes._node_helpers._resolve_router_decision",
                return_value=decision,
            )
        )
        stack.enter_context(
            patch(
                "app.agent.runtime.nodes.time.perf_counter",
                side_effect=[100.0, 100.012],
            )
        )

        resolved_decision, duration_ms = _resolve_router_decision(
            state={},
            normal_msgs=[],
            user_msg="查询农场状态",
            tools=[],
        )

    assert resolved_decision is decision
    assert duration_ms == 12


def test_runtime_router_uses_task_state_routing_input_when_relevant(
    monkeypatch,
) -> None:
    captured_messages: list[str] = []

    def fake_route_tools(message, runtime_tools, **_kwargs):
        captured_messages.append(message)
        return RouterDecision(selected_tools=["create_crop_cycle"])

    monkeypatch.setattr(_node_helpers, "_route_tools", fake_route_tools)

    _resolve_router_decision(
        state={
            "active_task_state": {
                "task_type": "planting_plan",
                "missing_information": ["种植面积"],
                "entities": {"crop": "玉米"},
            },
            "task_state_relevance": {
                "score": 0.9,
                "decision": "inject",
                "reason": "补充缺失面积",
                "should_inject": True,
            },
        },
        normal_msgs=[],
        user_msg="20亩",
        tools=[],
    )

    assert captured_messages
    assert "当前任务：planting_plan" in captured_messages[0]
    assert "缺失信息：种植面积" in captured_messages[0]
    assert "已知实体：crop=玉米" in captured_messages[0]
    assert "用户输入：20亩" in captured_messages[0]


def test_runtime_router_keeps_original_input_when_task_state_irrelevant(
    monkeypatch,
) -> None:
    captured_messages: list[str] = []

    def fake_route_tools(message, runtime_tools, **_kwargs):
        captured_messages.append(message)
        return RouterDecision(selected_tools=["weather"])

    monkeypatch.setattr(_node_helpers, "_route_tools", fake_route_tools)

    _resolve_router_decision(
        state={
            "active_task_state": {
                "task_type": "planting_plan",
                "missing_information": ["种植面积"],
            },
            "task_state_relevance": {
                "score": 0.1,
                "decision": "do_not_inject",
                "reason": "天气旁路",
                "should_inject": False,
            },
        },
        normal_msgs=[],
        user_msg="天气怎么样？",
        tools=[],
    )

    assert captured_messages == ["天气怎么样？"]


def test_record_router_plan_trace_preserves_router_duration() -> None:
    collector = MagicMock()
    decision = RouterDecision(selected_tools=["get_farm_status"])

    _node_helpers._record_router_plan_trace(
        collector=collector,
        router_decision=decision,
        user_msg="查询农场状态",
        farm_id=1,
        session_id="session-1",
        duration_ms=12,
    )

    collector.record.assert_called_once()
    assert collector.record.call_args.kwargs["node_name"] == "skill_router"
    assert collector.record.call_args.kwargs["duration_ms"] == 12


def test_record_router_plan_trace_separates_raw_and_augmented_input() -> None:
    collector = MagicMock()
    decision = RouterDecision(selected_tools=["create_crop_cycle"])

    payload = _node_helpers._record_router_plan_trace(
        collector=collector,
        router_decision=decision,
        user_msg="20亩",
        routing_augmented_input="当前任务：planting_plan\n用户输入：20亩",
        farm_id=1,
        session_id="session-1",
        duration_ms=12,
    )

    assert payload["raw_user_input"] == "20亩"
    assert payload["routing_augmented_input"] == (
        "当前任务：planting_plan\n用户输入：20亩"
    )
    assert collector.record.call_args.kwargs["input_data"] == {
        "message": "20亩",
        "routing_augmented": True,
    }


@pytest.mark.asyncio
async def test_llm_node_records_skill_router_trace() -> None:
    collector = MagicMock()
    fake_llm = _FakeLLM()
    user_msg = "查询农场状态" * 80
    decision = RouterDecision(
        selected_tools=["get_farm_status"],
        selected_operations={"get_farm_status": ["query_status"]},
        rejected_tools=["create_cost_record"],
        rejected_candidates=[
            {
                "name": "create_cost_record",
                "reason": "read_intent_write_operation",
            }
        ],
        schema_token_estimate=620,
        policy_violations=["write_tool_blocked"],
        fallback_reason="test_reason",
        scores={"domain": {"farm": 0.85}},
        evidence={"selected_candidates": [{"name": "get_farm_status"}]},
    )

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, collector)
        await _llm_node(
            {
                "messages": [HumanMessage(content=user_msg)],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-1",
                "router_decision": decision,
            }
        )

    router_trace = next(
        call
        for call in collector.record.call_args_list
        if call.kwargs.get("node_type") == "skill_router"
    )
    assert router_trace.kwargs["node_name"] == "skill_router"
    assert router_trace.kwargs["input_data"] == {
        "message": user_msg[:500],
        "routing_augmented": False,
    }
    output_data = router_trace.kwargs["output_data"]
    assert output_data["schema_version"] == 2
    assert output_data["selected"]["tools"] == ["get_farm_status"]
    assert output_data["selected"]["operations"] == {
        "get_farm_status": ["query_status"]
    }
    assert output_data["summary"]["fallback_reason"] == "test_reason"
    assert output_data["summary"]["policy_violations"] == ["write_tool_blocked"]
    assert output_data["recall"]["status"] == "skipped"
    assert output_data["recall"]["embedding_location"] == "none"
    assert output_data["candidate_explanations"][0]["route"] == "get_farm_status"
    assert output_data["plan"]["route_type"] == "read_plan"
    assert output_data["plan"]["validation"]["status"] == "valid"
    assert "frames" not in output_data
    assert "plan_draft" not in output_data
    assert "scores" not in output_data
    assert router_trace.kwargs["token_usage"] == {
        "schema_token_estimate": 620,
        "usage_source": "router_estimate",
    }
