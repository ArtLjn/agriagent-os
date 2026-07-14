"""Runtime RouterDecision 工具绑定测试。"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.router import RouterDecision
from app.agent.runtime.nodes import _llm_node
from app.context.models import ContextBundle

pytestmark = pytest.mark.no_db


def test_runtime_nodes_keeps_expand_by_chain_patch_hook() -> None:
    """runtime.nodes 保留 expand_by_chain patch 兼容入口。"""
    import app.agent.runtime.nodes as nodes

    assert hasattr(nodes, "expand_by_chain")


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeLLM:
    model_name = "fake-model"

    def __init__(self) -> None:
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools: list, **_kwargs):
        self.bound_tool_names = [tool.name for tool in tools]
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


def _runtime_patches(fake_llm: _FakeLLM, tools: list[_FakeTool]):
    return [
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes.get_langchain_tools", return_value=tools),
        patch("app.agent.runtime.nodes.get_llm", return_value=fake_llm),
        patch("app.agent.runtime.nodes._build_circuit_key", return_value="fake/model"),
        patch("app.agent.runtime.nodes._record_llm_success"),
        patch("app.agent.runtime.nodes._record_llm_failure"),
        patch(
            "app.agent.runtime.nodes._get_runtime_context_bundle",
            new=AsyncMock(side_effect=_empty_context_bundle),
        ),
        patch(
            "app.agent.runtime.nodes._get_farm_context",
            new=AsyncMock(return_value=_farm_context()),
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


def _enter_runtime_patches(
    stack: ExitStack, fake_llm: _FakeLLM, tools: list[_FakeTool]
) -> list[MagicMock]:
    entered = [
        stack.enter_context(patcher) for patcher in _runtime_patches(fake_llm, tools)
    ]
    prompt_cache = entered[9]
    prompt_cache.return_value.get.return_value = "系统提示"
    settings = entered[-1]
    settings.ai.parallel_tool_calls = False
    settings.ai.failover_max_retries = 1
    return entered


@pytest.mark.asyncio
async def test_llm_node_uses_prepared_router_selected_tools() -> None:
    """state 中的 RouterDecision 应限定 LLM 绑定工具集合。"""
    fake_llm = _FakeLLM()
    tools = [
        _FakeTool("get_farm_status"),
        _FakeTool("create_operation_work_order"),
    ]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        await _llm_node(
            {
                "messages": [HumanMessage(content="随便聊聊")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-1",
                "router_decision": RouterDecision(
                    selected_tools=["get_farm_status"],
                    context_dependencies=["crop_cycles"],
                ),
            }
        )

    assert fake_llm.bound_tool_names == ["get_farm_status"]


@pytest.mark.asyncio
async def test_llm_node_does_not_bind_disabled_selected_tool() -> None:
    fake_llm = _FakeLLM()
    disabled_tool = _FakeTool("web_search")
    disabled_tool.skill_metadata = type(
        "SkillMetadataStub",
        (),
        {"enabled": False},
    )()
    tools = [disabled_tool, _FakeTool("get_farm_status")]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        await _llm_node(
            {
                "messages": [HumanMessage(content="搜索一下天气新闻")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-disabled",
                "router_decision": RouterDecision(selected_tools=["web_search"]),
            }
        )

    assert fake_llm.bound_tool_names == []


@pytest.mark.asyncio
async def test_llm_node_returns_router_decision_for_tool_node_state() -> None:
    """LLM 节点应把本轮 RouterDecision 写回 state，供工具节点生成 pending plan。"""
    fake_llm = _FakeLLM()
    tools = [
        _FakeTool("manage_workers"),
        _FakeTool("create_operation_work_order"),
    ]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        result = await _llm_node(
            {
                "messages": [
                    HumanMessage(
                        content="我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了"
                    )
                ],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-1",
            }
        )

    router_decision = result["router_decision"]
    assert isinstance(router_decision, RouterDecision)
    assert [frame.intent for frame in router_decision.frames] == [
        "create_worker",
        "create_work_order",
    ]


@pytest.mark.asyncio
async def test_read_query_binds_router_selected_canonical_tool_only() -> None:
    """普通读请求只绑定 Router shortlist，tool name 使用 canonical capability。"""
    fake_llm = _FakeLLM()
    tools = [
        _FakeTool("manage_crop_cycle"),
        _FakeTool("get_farm_status"),
        _FakeTool("weather"),
        _FakeTool("create_operation_work_order"),
    ]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="我在种植哪些作物")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-1",
            }
        )

    assert result["router_decision"].tool_choice == "auto"
    assert result["router_decision"].selected_tools == ["manage_crop_cycle"]
    assert result["router_decision"].selected_operations == {
        "manage_crop_cycle": ["query_cycles"]
    }
    assert fake_llm.bound_tool_names == ["manage_crop_cycle"]


@pytest.mark.asyncio
async def test_model_choice_read_runtime_does_not_expand_to_all_read_tools() -> None:
    """fallback read 也只绑定 Router 预算内候选，不在 runtime fallback all。"""
    fake_llm = _FakeLLM()
    tools = [
        _FakeTool("get_cost_summary"),
        _FakeTool("get_debt_summary"),
        _FakeTool("get_farm_status"),
        _FakeTool("weather"),
        _FakeTool("create_cost_record"),
    ]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="我要看一下经营数据")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-model-choice",
            }
        )

    assert result["router_decision"].fallback == "model_choice_read_default"
    assert len(fake_llm.bound_tool_names) == 3
    assert "create_cost_record" not in fake_llm.bound_tool_names
    assert "weather" not in fake_llm.bound_tool_names


@pytest.mark.asyncio
async def test_llm_node_keeps_planting_planning_intent_in_read_tool_pool() -> None:
    """裸种植意向应先进入规划对话，不直接绑定创建茬口写工具。"""
    fake_llm = _FakeLLM()
    tools = [
        _FakeTool("get_farm_status"),
        _FakeTool("manage_crop_cycle"),
        _FakeTool("manage_crop_templates"),
    ]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="我想种黑布林的")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-planting",
            }
        )

    assert fake_llm.bound_tool_names == [
        "get_farm_status",
        "manage_crop_cycle",
    ]
    router_decision = result["router_decision"]
    assert router_decision.selected_tools == [
        "get_farm_status",
        "manage_crop_cycle",
    ]
    assert router_decision.fallback == "model_choice_read_default"


@pytest.mark.asyncio
async def test_final_answer_with_tool_result_binds_no_tools_by_default() -> None:
    """已有普通 ToolMessage 的 final answer 轮默认不重新绑定工具。"""
    fake_llm = _FakeLLM()
    tools = [
        _FakeTool("get_farm_status"),
        _FakeTool("create_operation_work_order"),
    ]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        await _llm_node(
            {
                "messages": [
                    HumanMessage(content="农场最近怎么样"),
                    ToolMessage(
                        content="【农场现状】\n水稻长势正常",
                        tool_call_id="tool-1",
                    ),
                ],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-1",
            }
        )

    assert fake_llm.bound_tool_names == []


@pytest.mark.asyncio
async def test_final_answer_with_tool_result_reuses_plan_and_context_trace() -> None:
    """已有工具结果的 final answer 轮不重复记录路由节点，并复用上下文。"""
    fake_llm = _FakeLLM()
    tools = [_FakeTool("weather")]
    collector = MagicMock()
    prepared_context = ContextBundle(blocks=[], token_budget=0, token_estimate=0)
    plan_draft = {
        "route_type": "read_plan",
        "selected_tools": ["weather"],
    }

    with ExitStack() as stack:
        entered = _enter_runtime_patches(stack, fake_llm, tools)
        context_loader = entered[6]
        entered[10].return_value = collector
        result = await _llm_node(
            {
                "messages": [
                    HumanMessage(content="天气怎么样"),
                    ToolMessage(
                        content="苏州晴，气温 32 度",
                        tool_call_id="tool-1",
                    ),
                ],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-1",
                "router_decision": RouterDecision(
                    selected_tools=["weather"],
                ),
                "plan_draft": plan_draft,
                "context_bundle": prepared_context,
            }
        )

    node_names = [
        call.kwargs.get("node_name") for call in collector.record.call_args_list
    ]
    assert "skill_router" not in node_names
    assert "tool_call_forced" not in node_names
    context_loader.assert_not_called()
    assert result["plan_draft"] is plan_draft
    assert result["context_bundle"] is prepared_context
    assert result["selected_tool_names"] == []
    assert isinstance(result["trace_round_index"], int)
