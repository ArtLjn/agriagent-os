"""Skill Router trace 数据测试。"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.router import IntentFrame, RouterDecision
from app.agent.runtime.nodes import _llm_node
from app.context.models import ContextBundle

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
    assert router_trace.kwargs["input_data"] == {"message": user_msg[:500]}
    assert (
        router_trace.kwargs["output_data"]["selected_tools"]
        == (decision.to_trace_payload()["selected_tools"])
    )
    assert (
        router_trace.kwargs["output_data"]["selected_operations"]
        == (decision.to_trace_payload()["selected_operations"])
    )
    assert (
        router_trace.kwargs["output_data"]["rejected_candidates"]
        == (decision.to_trace_payload()["rejected_candidates"])
    )
    assert router_trace.kwargs["output_data"]["fallback_reason"] == "test_reason"
    assert router_trace.kwargs["output_data"]["scores"] == {"domain": {"farm": 0.85}}
    assert router_trace.kwargs["output_data"]["plan_draft"]["route_type"] == (
        "read_plan"
    )
    assert router_trace.kwargs["output_data"]["plan_draft"]["selected_tools"] == [
        "get_farm_status"
    ]
    assert router_trace.kwargs["token_usage"] == {
        "schema_token_estimate": 620,
        "usage_source": "router_estimate",
    }
