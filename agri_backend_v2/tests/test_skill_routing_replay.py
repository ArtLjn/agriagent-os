"""按需运行的真实模型语义回放；只发送脱敏文本，绝不执行模型返回的业务工具。"""

import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from agent.domains.harness.memory import tools as memory_tools
from agent.domains.harness.router import SkillRouter
from agent.domains.harness.runtime.planner import MAKE_PLAN_TOOL_SCHEMA
from agent.domains.harness.tools.registry import SkillRegistry
from agent.prompts import render_system_prompt

# 默认 CI 不依赖外部模型。开启后也只校验工具选择，所有业务结果均来自下方合成样例。
pytestmark = pytest.mark.skipif(
    os.getenv("AGENT_ROUTING_LIVE") != "1", reason="仅显式开启时调用真实语义模型"
)
_assess = memory_tools.assess
_WEATHER_HISTORY = [
    {"role": "user", "content": "看看农场状态"},
    {"role": "assistant", "content": "当前有四个茬口，今天多云。要不要查天气？"},
]
_MEMORY_HISTORY = [
    {"role": "user", "content": "我喜欢吃西瓜"},
    {"role": "assistant", "content": "记忆系统出错了，没能保存。你还喜欢什么水果？"},
]
_CASES = [
    ("个人事情", "我明天有啥事情", _WEATHER_HISTORY, {"query_memos"}),
    ("个人提醒", "我明天有啥提醒", _WEATHER_HISTORY, {"query_memos"}),
    ("同义表达", "后天还有什么要记着做的？", [], {"query_memos"}),
    ("明确作业", "明天有哪些农事作业单？", [], {"query_work_orders"}),
    (
        "历史农事明细",
        "列出最近三天的农事日志明细，包括日期和参与工人",
        [],
        {"query_farm_logs"},
    ),
    ("农事汇总", "总结最近三天各类农事做了多少次", [], {"get_farm_review"}),
    ("天气预警", "明天苏州有什么气象预警？", [], {"get_weather"}),
    ("未结工资", "这个月工人的工资还有多少没结？", [], {"query_wages"}),
    ("材料支出", "最近化肥支出有哪些记录？", [], {"query_cost_records"}),
    (
        "多来源",
        "查一下我的备忘录，再查明天苏州天气",
        [],
        {"query_memos", "get_weather"},
    ),
    (
        "双记录来源",
        "备忘录和作业单都查一下，看明天要做什么",
        [],
        {"query_memos", "query_work_orders"},
    ),
    (
        "短回复",
        "查一下",
        [
            {"role": "user", "content": "之前让我记的事情还有吗？"},
            {"role": "assistant", "content": "要查询已保存的备忘录吗？"},
        ],
        {"query_memos"},
    ),
    ("当前纠正优先", "不是天气，我是问我存的提醒", _WEATHER_HISTORY, {"query_memos"}),
    ("普通偏好", "我喜欢吃西瓜", [], set()),
    ("偏好不继承故障", "我还喜欢草莓葡萄", _MEMORY_HISTORY, set()),
]


@pytest.fixture(scope="module")
def registry():
    return SkillRegistry.from_directory(Path(__file__).parents[1] / "agent" / "tools")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id,user_input,history,expected", _CASES, ids=[case[0] for case in _CASES]
)
async def test_live_main_agent_selects_correct_sources(
    registry, case_id, user_input, history, expected, monkeypatch
):
    from agent.domains.harness.runtime import engine, verify
    from agent.domains.harness.runtime.turn import Turn
    from agent.platforms.llm.client import MODEL, _async_client

    # 普通偏好验证实际运行时结果，而非假设模型一定不误选；存储边界一旦触及即失败。
    monkeypatch.setattr(memory_tools, "assess", _assess)
    storage = AsyncMock(side_effect=AssertionError("真实回放不得访问个人存储"))
    monkeypatch.setattr(memory_tools.store, "load", storage)
    turn = Turn(user_input=user_input, step_count=1, max_steps=1)
    tracker = verify.CallTracker()
    messages = [
        {"role": "system", "content": render_system_prompt()},
        *history,
        {"role": "user", "content": user_input + "\n[当前时间: 2026-10-23 15:00]"},
    ]
    tools = [*registry.exposed_tools(), MAKE_PLAN_TOOL_SCHEMA, memory_tools.TOOL_SCHEMA]
    observed = set()
    for _ in range(3):
        response = await _async_client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0,
            max_tokens=1600,
            timeout=45,
        )
        reply = response.choices[0].message
        calls = reply.tool_calls or []
        messages.append(
            {
                "role": "assistant",
                "content": reply.content or "",
                "tool_calls": [call.model_dump() for call in calls],
            }
        )
        for call in calls:
            selected = {call.function.name}
            if not expected:
                assert selected == {memory_tools.TOOL_NAME}, case_id
                events = [
                    event
                    async for event in engine._dispatch_tool_calls(
                        tool_calls=[
                            {
                                "id": call.id,
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            }
                        ],
                        rationale="普通偏好回放",
                        skill_index={},
                        skill_ctx=None,
                        approval_waiter=AsyncMock(),
                        turn=turn,
                        tracker=tracker,
                        plan_box={},
                    )
                ]
                result = next(
                    event["data"]["result"]
                    for event in events
                    if event["type"] == "observation"
                )
                # 错误参数仍应被拒绝；测试最终答复恢复，不把工具层拒绝伪装成成功。
                assert result.get("persisted") is False
                assert not verify.has_write_call(tracker)
                messages.append(turn.messages[-1])
                continue
            if call.function.name == "make_plan":
                selected = {
                    step["skill"]
                    for step in json.loads(call.function.arguments)["steps"]
                }
            assert selected <= expected, (
                f"{case_id}: 不相关的工具 {selected - expected}"
            )
            observed.update(selected)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": call.function.name,
                    "content": json.dumps(
                        {
                            "items": [{"id": 1, "title": "2026-10-24 早上打药"}],
                            "total": 1,
                            "date": "2026-10-24",
                            "weather": "多云",
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        if (expected and expected <= observed) or not calls:
            break
    assert expected <= observed, f"{case_id}: 缺少 {expected - observed}"
    if not expected:
        assert not calls, "模型未能从无写入结果正常收尾"
        _ = [
            event
            async for event in engine._emit_final_answer(
                turn, reply.content or "", None, tracker
            )
        ]
        assert turn.status == "completed", turn.final_answer
        assessment = await _assess(user_input, reply=turn.final_answer)
        assert not assessment.claims_persistence
        assert not assessment.claims_memory_failure
        storage.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case_id,user_input,history,expected",
    _CASES[:-2],
    ids=[case[0] for case in _CASES[:-2]],
)
async def test_live_router_retains_required_capabilities(
    registry, case_id, user_input, history, expected
):
    route = await SkillRouter(timeout_seconds=45).route(
        user_input, registry, history=history
    )
    # 真实模型错误不能靠全量降级蒙混成评测成功；仅允许有明确语义原因的不确定性降级。
    assert not (route.error or "").startswith("router_failed"), route.error
    candidates = (
        registry.tools_for_router_skills(route.selected_skills)
        if route.status == "selected"
        else registry.exposed_tools()
    )
    names = {tool["function"]["name"] for tool in candidates}
    assert expected <= names, f"{case_id}: 丢失 {expected - names}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_input,reply,explicit,ordinary",
    [
        ("我喜欢吃西瓜", "我已经长期记住了", False, True),
        (
            "我还喜欢草莓葡萄",
            "记忆系统再次出错，没能保存，只能先在当前对话参考。",
            False,
            True,
        ),
        ("请长期记住我喜欢西瓜", "还没有保存", True, False),
        ("提醒我明早打药", "备忘录已保存并置顶", False, False),
    ],
)
async def test_live_memory_distinguishes_observation_and_explicit_storage(
    user_input, reply, explicit, ordinary
):
    result = await _assess(user_input, reply=reply)
    assert result.requests_persistence is explicit
    assert result.preference_statement is ordinary
    if "没能保存" in reply:
        assert not result.claims_persistence
        assert result.claims_memory_failure
