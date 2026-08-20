"""Session View、Short Memory 和 ContextBundle 的 focused 回归测试。"""

from __future__ import annotations

from agent.domains.harness.context import builder as context
from agent.domains.harness.memory import service as memory
from agent.domains.harness.context.models import ContextBlockStatus


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
