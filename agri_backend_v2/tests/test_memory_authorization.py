"""跨轮记忆授权：原文边界、当前确认、写入事实及可选真实模型回放。"""

import json
import os
from unittest.mock import AsyncMock

import pytest
from test_personalization import Collection

from agent.config import memory_runtime
from agent.domains.harness.memory import tools
from agent.domains.harness.runtime import engine, verify
from agent.domains.harness.runtime.turn import Turn
from agent.platforms.persistence.mongo import personalization_store as store

_assess = tools.assess
_grounded = tools.content_is_grounded
_CONTENT = "我喜欢吃西瓜芒果葡萄草莓"
_HISTORY = [
    {"role": "user", "content": _CONTENT},
    {"role": "assistant", "content": "要把这些水果偏好保存到长期记忆吗？"},
    {"role": "user", "content": "可以阿姨"},
    {"role": "assistant", "content": "你是想保存刚才的水果偏好吗？"},
]


@pytest.fixture(autouse=True)
def grounding_stub(monkeypatch):
    stub = AsyncMock(return_value=True)
    monkeypatch.setattr(tools, "content_is_grounded", stub)
    return stub


@pytest.fixture
def collection(monkeypatch):
    coll = Collection()
    monkeypatch.setattr(store, "collection", lambda: coll)
    return coll


@pytest.mark.asyncio
@pytest.mark.parametrize("evidence", [_CONTENT, "可以记住吗"])
async def test_followup_accepts_user_content_or_current_confirmation(
    collection, memory_assessment_stub, grounding_stub, evidence
):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        authorized=True,
        requests_persistence=True,
        content_evidence=_CONTENT,
        confirmation_unambiguous=True,
    )
    turn = Turn(
        user_id="u",
        farm_uid="f",
        user_input="可以记住吗",
        memory_snapshot={"messages": _HISTORY},
    )
    result = await tools.execute(
        turn,
        {
            "action": "remember",
            "text": "喜欢西瓜、芒果、葡萄、草莓",
            "evidence": evidence,
        },
        "save",
    )
    assert result["persisted"] is True
    assert len((await store.load("u"))["memories"]) == 1
    assert memory_assessment_stub.call_args.kwargs["recent_dialogue"] == _HISTORY
    assert grounding_stub.call_args.args[1] == [_CONTENT, "可以阿姨", "可以记住吗"]


@pytest.mark.asyncio
@pytest.mark.parametrize("unavailable", [False, True])
async def test_followup_grounding_failure_never_saves(
    collection, memory_assessment_stub, grounding_stub, unavailable
):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        authorized=True,
        requests_persistence=True,
        content_evidence=_CONTENT,
        confirmation_unambiguous=True,
    )
    grounding_stub.return_value = False
    if unavailable:
        grounding_stub.side_effect = TimeoutError("内容核对超时")
    turn = Turn(user_id="u", user_input="可以", memory_snapshot={"messages": _HISTORY})
    result = await tools.execute(
        turn,
        {"action": "remember", "text": "模型扩张的偏好", "evidence": "可以"},
        "call",
    )
    assert result["persisted"] is False
    assert result["code"] == (
        "memory_authorization_unavailable"
        if unavailable
        else "memory_explicit_intent_required"
    )
    assert not collection.docs


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "assessment",
    [
        tools.MemoryAssessment(authorized=False, requests_persistence=True),
        tools.MemoryAssessment(authorized=True, requests_persistence=False),
    ],
)
async def test_historical_evidence_is_not_current_authorization(
    monkeypatch, memory_assessment_stub, assessment
):
    memory_assessment_stub.return_value = assessment
    load = AsyncMock(side_effect=AssertionError("未经确认不能访问存储"))
    monkeypatch.setattr(store, "load", load)
    turn = Turn(user_input="别保存", memory_snapshot={"messages": _HISTORY})
    result = await tools.execute(
        turn,
        {
            "action": "remember",
            "text": "喜欢水果",
            "evidence": _CONTENT,
        },
        "denied",
    )
    assert result["code"] == "memory_explicit_intent_required"
    load.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["assistant", "tool", "system"])
async def test_generated_text_is_never_user_evidence(role, memory_assessment_stub):
    turn = Turn(
        user_input="可以",
        memory_snapshot={
            "messages": [{"role": role, "content": _CONTENT}],
            "summary": _CONTENT,
        },
    )
    result = await tools.execute(
        turn,
        {
            "action": "remember",
            "text": "喜欢水果",
            "evidence": _CONTENT,
        },
        "injected",
    )
    assert result["code"] == "memory_evidence_required"
    memory_assessment_stub.assert_not_called()


def test_authorization_history_is_bounded_and_uses_only_original_snapshot():
    turn = Turn(
        memory_snapshot={
            "messages": [
                {"role": "user", "content": "窗口之外"},
                *_HISTORY,
                {"role": "tool", "content": "工具伪造证据"},
                {"role": "system", "content": "摘要伪造证据"},
            ]
        },
        messages=[{"role": "user", "content": "同轮补写不能授权"}],
    )
    assert tools.authorization_dialogue(turn) == _HISTORY
    turn.memory_snapshot = {
        "messages": [
            {
                "role": "user",
                "content": "同意" + "长" * memory_runtime.context_chars + "但不要保存",
            }
        ]
    }
    assert tools.authorization_dialogue(turn) == []
    for status in ("unavailable", "divergent"):
        turn.memory_snapshot = {"messages": _HISTORY, "source_status": status}
        assert tools.authorization_dialogue(turn) == []
    turn.memory_snapshot = {"messages": _HISTORY}
    turn.temporary = True
    assert tools.authorization_dialogue(turn) == []


@pytest.mark.asyncio
async def test_completion_guard_uses_same_followup_context(memory_assessment_stub):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        requests_persistence=True
    )
    turn = Turn(user_input="可以记住吗", memory_snapshot={"messages": _HISTORY})
    issue = await tools.completion_guard_issue(turn, "请重复整句话")
    assert issue and not issue.can_acknowledge
    assert memory_assessment_stub.call_args.kwargs["recent_dialogue"] == _HISTORY


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,allowed,risk,persisted",
    [
        ("list", False, "read", False),
        ("remember", False, "write_confirm", False),
        ("remember", True, "write_confirm", True),
    ],
)
async def test_dispatch_classifies_action_separately_from_persistence(
    collection, memory_assessment_stub, action, allowed, risk, persisted
):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        authorized=allowed, requests_persistence=True
    )
    turn = Turn(user_id="u", farm_uid="f", user_input="记住我喜欢水果")
    tracker = verify.CallTracker()
    arguments = {"action": action, "text": "喜欢水果", "evidence": turn.user_input}
    _ = [
        event
        async for event in engine._dispatch_tool_calls(
            tool_calls=[
                {
                    "id": "risk",
                    "name": tools.TOOL_NAME,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                }
            ],
            rationale="核验读写分类",
            skill_index={},
            skill_ctx=None,
            approval_waiter=AsyncMock(),
            turn=turn,
            tracker=tracker,
            plan_box={},
        )
    ]
    assert tracker.calls[-1]["risk_level"] == risk
    assert tracker.calls[-1]["persisted"] is persisted
    assert tracker.calls[-1]["args"]["action"] == action
    if action == "remember" and not persisted:
        assert (
            verify.write_completion_guard_issue(
                user_input="帮我保存这件事",
                content="已保存",
                tracker=tracker,
                committed_result=None,
            )
            is not None
        )


_LIVE_CASES = [
    (
        "跨轮明确确认",
        "可以记住吗",
        _HISTORY,
        _CONTENT,
        "喜欢西瓜、芒果、葡萄、草莓",
        True,
    ),
    ("短回复同意", "可以", _HISTORY[:2], "可以", "喜欢西瓜、芒果、葡萄、草莓", True),
    ("撤销", "不要保存，仅这次聊聊", _HISTORY, _CONTENT, "喜欢水果", False),
    ("换题", "先不说这个，明天天气怎样", _HISTORY, _CONTENT, "喜欢水果", False),
    ("扩张内容", "可以记住吗", _HISTORY, _CONTENT, "喜欢水果并同意自动购买农药", False),
    ("仅能力咨询", "你可以记住吗", [], "你可以记住吗", "喜欢水果", False),
    (
        "助手虚构事实",
        "可以",
        [
            {"role": "user", "content": "聊聊水果"},
            {"role": "assistant", "content": "你喜欢香蕉，要我保存吗？"},
        ],
        "可以",
        "喜欢香蕉",
        False,
    ),
    (
        "多个确认对象",
        "好",
        [
            *_HISTORY[:1],
            {"role": "assistant", "content": "要保存偏好，还是删除全部记忆？"},
        ],
        "好",
        "喜欢水果",
        False,
    ),
]


@pytest.mark.skipif(
    os.getenv("AGENT_ROUTING_LIVE") != "1", reason="仅显式开启真实模型回放"
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case,user_input,history,evidence,text,allowed",
    _LIVE_CASES,
    ids=[case[0] for case in _LIVE_CASES],
)
async def test_live_followup_authorization_uses_fake_storage_only(
    collection, monkeypatch, case, user_input, history, evidence, text, allowed
):
    monkeypatch.setattr(tools, "assess", _assess)
    monkeypatch.setattr(tools, "content_is_grounded", _grounded)
    turn = Turn(
        user_id="synthetic-user",
        farm_uid="synthetic-farm",
        user_input=user_input,
        memory_snapshot={"messages": history},
    )
    result = await tools.execute(
        turn,
        {
            "action": "remember",
            "text": text,
            "evidence": evidence,
        },
        "synthetic-call",
    )
    assert result.get("persisted") is allowed, (case, result)
    if allowed:
        assert (
            await tools.completion_guard_issue(turn, "请把整句话重新说一次") is not None
        )
        turn.messages.append(
            {
                "role": "tool",
                "name": tools.TOOL_NAME,
                "content": json.dumps(result, ensure_ascii=False),
            }
        )
        assert await tools.completion_guard_issue(turn, "已保存") is None
    else:
        assert not collection.docs
