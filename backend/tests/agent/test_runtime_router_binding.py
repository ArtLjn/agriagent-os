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
