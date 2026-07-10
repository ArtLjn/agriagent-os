"""Runtime 最终回复前 Reflection 接入测试。"""

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.reflector import (
    ReflectionDecision,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
)
from app.agent.reflector.models import ReflectionIssue
from app.agent.router import RouterDecision
from app.agent.runtime.nodes import _llm_node
from app.agent.runtime.reflection import apply_post_tool_reflection
from app.context.models import ContextBundle

pytestmark = pytest.mark.no_db


class _FakeTool:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeLLM:
    model_name = "fake-model"

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.bound_tool_names: list[str] = []

    def bind_tools(self, tools: list, **_kwargs):
        self.bound_tool_names = [tool.name for tool in tools]
        return self

    async def ainvoke(self, _messages):
        return AIMessage(content=self.response_text, tool_calls=[])


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
) -> None:
    entered = [
        stack.enter_context(patcher) for patcher in _runtime_patches(fake_llm, tools)
    ]
    prompt_cache = entered[8]
    prompt_cache.return_value.get.return_value = "系统提示"
    settings = entered[-1]
    settings.ai.parallel_tool_calls = False
    settings.ai.failover_max_retries = 1


def _reflection_result(
    decision: ReflectionDecision,
    *,
    reason: str,
) -> ReflectionResult:
    return ReflectionResult(
        trigger=ReflectionTrigger.POST_TOOL_RESULT,
        decision=decision,
        reason=reason,
        issues=[
            ReflectionIssue(
                code="runtime_reflection_test",
                severity=ReflectionSeverity.BLOCKER,
                message=reason,
                suggested_decision=decision,
            )
        ],
    )


@pytest.mark.asyncio
async def test_tool_failure_success_reply_is_rewritten_by_reflection() -> None:
    fake_llm = _FakeLLM("已查询成功。")
    tools = [_FakeTool("get_farm_status")]
    safe_reason = "工具结果与回复不一致：工具调用失败但回复声称成功。"

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        reflector_cls = stack.enter_context(
            patch("app.agent.runtime.reflection.ReflectorService", create=True)
        )
        reflector_cls.return_value.check_tool_response.return_value = (
            _reflection_result(
                ReflectionDecision.FALLBACK_RESPONSE,
                reason=safe_reason,
            )
        )

        result = await _llm_node(
            {
                "messages": [
                    HumanMessage(content="农场最近怎么样"),
                    ToolMessage(
                        content="工具调用失败：数据库连接失败",
                        tool_call_id="tc-status",
                    ),
                ],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-reflection-failure",
            }
        )

    final_message = result["messages"][0]
    assert final_message.content == safe_reason
    assert "已查询成功" not in final_message.content
    reflector_cls.return_value.check_tool_response.assert_called_once()
    call_kwargs = reflector_cls.return_value.check_tool_response.call_args.kwargs
    assert call_kwargs["selected_tools"] == []
    assert call_kwargs["tool_messages"][0].tool_call_id == "tc-status"
    assert call_kwargs["trace_metadata"]["farm_id"] == 1
    assert call_kwargs["trace_metadata"]["session_id"] == "session-reflection-failure"
    assert call_kwargs["trace_metadata"]["intent"] == "agent"
    assert call_kwargs["trace_metadata"]["selected_tools"] == []
    assert call_kwargs["trace_metadata"]["tool_call_ids"] == ["tc-status"]
    assert call_kwargs["trace_metadata"]["response_preview"] == "已查询成功。"


@pytest.mark.asyncio
async def test_low_risk_chitchat_does_not_instantiate_reflector() -> None:
    fake_llm = _FakeLLM("你好，有什么我可以帮你？")

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, [])
        reflector_cls = stack.enter_context(
            patch("app.agent.runtime.reflection.ReflectorService", create=True)
        )

        result = await _llm_node(
            {
                "messages": [HumanMessage(content="你好")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "greeting",
                "user_id": "user-1",
                "session_id": "session-chitchat",
                "router_decision": RouterDecision(selected_tools=[]),
            }
        )

    assert result["messages"][0].content == "你好，有什么我可以帮你？"
    reflector_cls.assert_not_called()


@pytest.mark.asyncio
async def test_no_tool_write_success_claim_returns_fail_closed_reply() -> None:
    fake_llm = _FakeLLM("已记录李海这个月干了15天压瓜。")

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, [])

        result = await _llm_node(
            {
                "messages": [HumanMessage(content="李海这个月干了15天压瓜")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-no-tool-write-claim",
                "router_decision": RouterDecision(selected_tools=[]),
            }
        )

    final_text = result["messages"][0].content
    assert (
        final_text
        == "这条操作还没有执行。请重新描述要记录或修改的内容，我会先生成待确认操作，确认后再执行。"
    )
    assert "已记录" not in final_text
    assert "没有工具写入结果" not in final_text


def test_no_tool_write_success_trace_metadata_includes_plan_draft() -> None:
    plan_draft = {
        "route_type": "write_pending_action",
        "steps": [
            {
                "tool_name": "create_operation_work_order",
                "params": {"worker_name": "李海", "operation_type": "压瓜"},
            }
        ],
        "validation": {"status": "passed"},
    }

    with patch("app.agent.runtime.reflection.ReflectorService", create=True) as (
        reflector_cls
    ):
        reflector_cls.return_value.check_tool_response.return_value = (
            _reflection_result(
                ReflectionDecision.FALLBACK_RESPONSE,
                reason="没有工具写入结果或待确认动作，但最终回复声称业务数据已经写入。",
            )
        )

        apply_post_tool_reflection(
            response=AIMessage(content="已记录李海这个月干了15天压瓜。"),
            tool_messages=[],
            selected_tool_names=[],
            farm_id=1,
            session_id="session-plan-draft-reflection",
            intent="agent",
            user_message="李海这个月干了15天压瓜",
            plan_draft=plan_draft,
        )

    call_kwargs = reflector_cls.return_value.check_tool_response.call_args.kwargs
    assert call_kwargs["trace_metadata"]["plan_draft"] == plan_draft


@pytest.mark.asyncio
async def test_required_selected_tool_missing_returns_safe_fallback() -> None:
    fake_llm = _FakeLLM("你现在有两个茬口。")
    tools = [_FakeTool("get_farm_status")]
    safe_reason = "需要先调用工具获取真实数据，请稍后重试。"

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        reflector_cls = stack.enter_context(
            patch("app.agent.runtime.reflection.ReflectorService", create=True)
        )
        reflector_cls.return_value.check_tool_response.return_value = (
            _reflection_result(
                ReflectionDecision.REQUIRE_TOOL,
                reason="Router 已选择工具，但回复直接给出了业务事实。",
            )
        )

        result = await _llm_node(
            {
                "messages": [HumanMessage(content="农场最近怎么样")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-require-tool",
                "router_decision": RouterDecision(selected_tools=["get_farm_status"]),
            }
        )

    assert result["messages"][0].content == safe_reason
    assert "两个茬口" not in result["messages"][0].content
    reflector_cls.return_value.check_tool_response.assert_called_once()
    call_kwargs = reflector_cls.return_value.check_tool_response.call_args.kwargs
    assert call_kwargs["selected_tools"] == ["get_farm_status"]
    assert call_kwargs["tool_calls"] == []
    assert call_kwargs["trace_metadata"]["tool_call_ids"] == []
    assert call_kwargs["trace_metadata"]["response_preview"] == "你现在有两个茬口。"


@pytest.mark.asyncio
async def test_planning_reply_with_read_tools_is_not_rewritten() -> None:
    planning_reply = (
        "十几亩可以先按 15 亩左右做试种规划。建议先确认地块位置、排水、"
        "租期和投入预算，再决定是否建茬口。"
    )
    fake_llm = _FakeLLM(planning_reply)
    tools = [
        _FakeTool("get_crop_cycles"),
        _FakeTool("get_crop_templates"),
    ]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        result = await _llm_node(
            {
                "messages": [HumanMessage(content="我打算租个十几亩种种")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-planting-planning",
                "router_decision": RouterDecision(
                    selected_tools=["get_crop_cycles", "get_crop_templates"],
                ),
            }
        )

    assert result["messages"][0].content == planning_reply
    assert fake_llm.bound_tool_names == [
        "get_crop_cycles",
        "get_crop_templates",
    ]


@pytest.mark.asyncio
async def test_tool_result_final_number_contradiction_uses_safe_reply() -> None:
    fake_llm = _FakeLLM("你现在有 3 个茬口。")
    tools = [_FakeTool("get_farm_status")]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)

        result = await _llm_node(
            {
                "messages": [
                    HumanMessage(content="农场最近怎么样"),
                    ToolMessage(
                        content="查询结果：当前共有 2 个茬口。",
                        tool_call_id="tc-status",
                    ),
                ],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-contradiction",
            }
        )

    final_text = result["messages"][0].content
    assert final_text == "工具结果与最终回复中的关键数量不一致。"
    assert "3 个茬口" not in final_text


@pytest.mark.asyncio
async def test_missing_write_tool_call_keeps_fail_closed_reply() -> None:
    fail_closed_text = (
        "这条操作还没有执行。系统没有生成可确认的待执行动作。"
        "请重新描述要新增、修改或结算的对象和关键参数，"
        "我会先生成待确认操作，确认后再执行。"
    )
    fake_llm = _FakeLLM(fail_closed_text)
    tools = [_FakeTool("create_cost_record")]

    with ExitStack() as stack:
        _enter_runtime_patches(stack, fake_llm, tools)
        reflector_cls = stack.enter_context(
            patch("app.agent.runtime.reflection.ReflectorService", create=True)
        )
        reflector_cls.return_value.check_tool_response.return_value = (
            _reflection_result(
                ReflectionDecision.REQUIRE_TOOL,
                reason="写操作需要先生成待确认动作。",
            )
        )

        result = await _llm_node(
            {
                "messages": [HumanMessage(content="买了200块化肥")],
                "farm_id": 1,
                "farm_uid": "farm-uid-1",
                "intent": "agent",
                "user_id": "user-1",
                "session_id": "session-write-missing-tool",
                "router_decision": RouterDecision(
                    selected_tools=["create_cost_record"]
                ),
            }
        )

    assert result["messages"][0].content == fail_closed_text
    assert "获取真实数据" not in result["messages"][0].content
    reflector_cls.return_value.check_tool_response.assert_called_once()
