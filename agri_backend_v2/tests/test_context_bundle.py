"""Session View、Short Memory 和 ContextBundle 的 focused 回归测试。"""

from __future__ import annotations

import pytest

from agent.domains.harness.context import builder as context
from agent.domains.harness.memory import service as memory
from agent.domains.harness.context.models import ContextBlockStatus
from agent.platforms.persistence.mongo import chat_store


async def _capture_state(**kwargs):
    return kwargs


def test_short_memory_summary_is_separate_and_long_memory_is_opt_in() -> None:
    bundle = context.build_context_bundle(
        "那后天呢",
        {
            "conversation_id": "conv-1",
            "conversation_revision": 8,
            "summary_revision": 3,
            "source_status": "mongo",
            "summary": "用户正在追问苏州天气，前一轮已确认地点。",
            "messages": [
                {"role": "user", "content": "明天天气"},
                {"role": "assistant", "content": "明天有雨"},
            ],
            "memory_hits": [{"content": "用户偏好农场 A"}],
        },
    )

    included = {
        item.key: item
        for item in bundle.blocks
        if item.status == ContextBlockStatus.INCLUDED
    }
    assert "session_summary" in included
    assert "recent_turns" in included
    assert "memory_hits" not in included
    assert bundle.summary_revision == 3
    assert bundle.source_status.value == "mongo"

    messages = context.bundle_to_messages(bundle)
    assert any("后天" in item["content"] for item in messages if item["role"] == "user")
    assert any("窗口外的摘要" in item["content"] for item in messages)


def test_pending_action_is_required_and_budget_drops_low_priority(monkeypatch) -> None:
    monkeypatch.setattr(context.tokenizer, "get_model_context", lambda _model: 120)
    bundle = context.build_context_bundle(
        "确认",
        {
            "conversation_id": "conv-2",
            "pending_action": {"type": "write_confirm", "expires_at": "2030-01-01"},
            "summary": "很长的历史摘要。" * 200,
            "messages": [],
        },
    )
    pending = next(item for item in bundle.blocks if item.key == "pending_action")
    assert pending.required is True
    assert pending.status == ContextBlockStatus.INCLUDED
    assert bundle.budget.decision.value in {"dropped", "exceeded"}
    summary = next(item for item in bundle.blocks if item.key == "session_summary")
    assert summary.status == ContextBlockStatus.DROPPED


def test_session_view_reports_unavailable_without_mongo(monkeypatch) -> None:
    from agent import config

    monkeypatch.setattr(config.settings.mongodb, "enabled", False)
    view = __import__("asyncio").run(memory.get_session_view("conv-3"))

    assert view["source_status"] == "unavailable"
    assert view["messages"] == []
    assert view["summary"] is None


def test_mongo_unavailable_does_not_fallback_to_local_history(monkeypatch) -> None:
    from agent import config
    from agent.platforms.persistence.mongo import chat_store

    monkeypatch.setattr(config.settings.mongodb, "enabled", True)
    monkeypatch.setattr(
        chat_store,
        "get_conversation_state",
        lambda *_args, **_kwargs: _async_value(
            {"status": "unavailable", "source_status": "unavailable"}
        ),
    )
    view = __import__("asyncio").run(memory.get_session_view("conv-unavailable"))

    assert view["source_status"] == "unavailable"
    assert view["messages"] == []


def test_recent_projection_keeps_complete_turns() -> None:
    history = [
        {"role": "user", "content": "第一轮"},
        {"role": "assistant", "content": "答复一"},
        {"role": "user", "content": "第二轮"},
        {"role": "assistant", "content": "答复二"},
        {"role": "user", "content": "未完成"},
    ]
    projected = memory.project_recent_turns(history, recent_turn_limit=1)
    assert projected == [
        {"role": "user", "content": "第二轮"},
        {"role": "assistant", "content": "答复二"},
    ]


def test_multiturn_projection_combines_summary_pending_and_recent_complete_turns() -> None:
    history = []
    for index in range(4):
        history.extend(
            [
                {"role": "user", "content": f"问题 {index}"},
                {"role": "assistant", "content": f"答复 {index}"},
            ]
        )
    recent = memory.project_recent_turns(history, recent_turn_limit=2)
    bundle = context.build_context_bundle(
        "继续处理",
        {
            "conversation_id": "conv-multiturn",
            "conversation_revision": 4,
            "summary_revision": 1,
            "summary": "前两轮已经确认农场范围。",
            "messages": recent,
            "pending_action": {"type": "write_confirm", "status": "pending"},
            "source_status": "mongo",
        },
    )

    included = {
        item.key for item in bundle.blocks if item.status == ContextBlockStatus.INCLUDED
    }
    assert recent == [
        {"role": "user", "content": "问题 2"},
        {"role": "assistant", "content": "答复 2"},
        {"role": "user", "content": "问题 3"},
        {"role": "assistant", "content": "答复 3"},
    ]
    assert {"session_summary", "recent_turns", "pending_action"} <= included


def test_session_actions_receive_lifecycle_metadata(monkeypatch) -> None:
    from agent import config

    monkeypatch.setattr(
        config.settings.context.conversation_state,
        "pending_action_ttl_seconds",
        60,
    )
    monkeypatch.setattr(
        config.settings.context.conversation_state,
        "task_state_ttl_seconds",
        120,
    )

    pending = memory.prepare_pending_action(
        {"tool_name": "create_farm_log"}, turn_id="turn-1"
    )
    task = memory.prepare_task_state({"task_id": "task-1"}, turn_id="turn-1")

    assert pending["status"] == "pending"
    assert pending["source_turn_id"] == "turn-1"
    assert pending["expires_at"]
    assert task["status"] == "active"
    assert task["source_turn_id"] == "turn-1"
    assert task["expires_at"]


@pytest.mark.asyncio
async def test_persist_session_turn_clears_previous_task_state(monkeypatch) -> None:
    monkeypatch.setattr(chat_store, "save_conversation_state", _capture_state)

    result = await memory.persist_session_turn(
        conversation_id="conversation-1",
        user_id="user-1",
        farm_id=1,
        farm_uid="farm-1",
        expected_revision=2,
        turn_id="turn-2",
        task_state=None,
    )

    assert result["task_state"] is None


async def _async_value(value):
    return value
