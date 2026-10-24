"""真实 Memory Service 与存储协议的组合回归，外部 Mongo/LLM 使用内存替身。"""

import asyncio
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest
from test_chat_store_state import fake_state_store as fake_state_store

from agent.config import settings
from agent.domains.harness.context import summarizer
from agent.domains.harness.memory import short_term
from agent.platforms.persistence.mongo import chat_store, conversation_state

SCOPE = {"user_id": "user-1", "farm_id": 1}


def history(count):
    """生成具有稳定消息顺序和 Turn 身份的历史事实。"""
    return [
        {
            "role": role,
            "turn_id": f"turn-{index}",
            "message_id": f"{index * 2 + offset:024x}",
            "content": f"{role}-{index}",
            "createdAt": "2026-01-01 00:00:00.000000",
        }
        for index in range(count)
        for offset, role in enumerate(("user", "assistant"))
    ]


@pytest.fixture
def memory_store(fake_state_store, monkeypatch):
    monkeypatch.setattr(settings.mongodb, "enabled", True)
    monkeypatch.setattr(settings.context.conversation_state, "recent_turn_limit", 6)
    messages = history(7)

    async def load_recent(_conversation_id, *, limit, reset_at=None, **kwargs):
        eligible = [
            item for item in messages if not reset_at or item["createdAt"] > reset_at
        ]
        return deepcopy(eligible[-limit:])

    monkeypatch.setattr(chat_store, "load_recent", load_recent)
    monkeypatch.setattr(
        summarizer, "chat", lambda _messages: {"content": "已确认地块 A"}
    )
    return fake_state_store, messages


@pytest.mark.asyncio
async def test_approval_transitions_and_finalization_are_distinct_idempotent_writes(
    fake_state_store,
):
    common = dict(
        conversation_id="approval", farm_uid="farm-1", turn_id="turn-1", **SCOPE
    )
    first = await short_term.persist_session_turn(
        **common,
        expected_revision=0,
        pending_action={"tool_call_id": "call-1"},
    )
    retry = await short_term.persist_session_turn(
        **common,
        expected_revision=0,
        pending_action={"tool_call_id": "call-1"},
    )
    second = await short_term.persist_session_turn(
        **common,
        expected_revision=first["conversation_revision"],
        pending_action={"tool_call_id": "call-2"},
    )
    done = await short_term.persist_session_turn(
        **common,
        expected_revision=second["conversation_revision"],
        pending_action=None,
    )
    repeated_done = await short_term.persist_session_turn(
        **common,
        expected_revision=second["conversation_revision"],
        pending_action=None,
    )
    assert retry["status"] == repeated_done["status"] == "idempotent"
    assert done["pending_action"] is None
    assert done["conversation_revision"] == 3


def test_interleaved_queued_messages_are_paired_by_turn_id():
    messages = history(2)
    queued = [messages[0], messages[2], messages[1], messages[3]]
    turns = short_term.complete_turns(queued)
    assert [[m["turn_id"] for m in pair] for pair in turns] == [
        ["turn-0", "turn-0"],
        ["turn-1", "turn-1"],
    ]
    assert (
        short_term.complete_turns(
            [
                {"role": "user", "content": "旧消息无 ID"},
                messages[1],
            ]
        )
        == []
    )


@pytest.mark.asyncio
async def test_short_history_rolls_into_summary_before_leaving_window(
    memory_store, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        summarizer,
        "chat",
        lambda messages: calls.append(messages) or {"content": "地块 A"},
    )
    first = await short_term.get_session_view("rolling", **SCOPE)
    assert first["summary"] == "地块 A"
    assert len(first["messages"]) == 12
    assert first["messages"][0]["turn_id"] == "turn-1"
    assert first["recent_user_statements"][0] == "user-0"
    await short_term.get_session_view("rolling", **SCOPE)
    assert len(calls) == 1
    # 下一轮摘要合并上一份摘要，只处理新滑出的轮次。
    memory_store[1].extend(history(8)[-2:])
    await short_term.get_session_view("rolling", **SCOPE)
    assert len(calls) == 2
    assert "地块 A" in calls[-1][-1]["content"]
    assert "user-1" in calls[-1][-1]["content"]
    assert "user-0" not in calls[-1][-1]["content"]


@pytest.mark.asyncio
async def test_user_evidence_survives_six_turn_window_and_is_bounded(memory_store):
    messages = memory_store[1]
    messages[:] = history(14)
    messages[6]["content"] = "我喜欢打王者荣耀，下午健身再做饭"
    view = await short_term.get_session_view("user-evidence", **SCOPE)
    assert all("王者荣耀" not in m["content"] for m in view["messages"])
    assert "我喜欢打王者荣耀，下午健身再做饭" in view["recent_user_statements"]
    assert (
        len(view["recent_user_statements"])
        == short_term.SESSION_USER_EVIDENCE_TURN_LIMIT - 1
    )
    assert "user-0" not in view["recent_user_statements"]
    assert all(
        not text.startswith("assistant") for text in view["recent_user_statements"]
    )


@pytest.mark.asyncio
async def test_pending_prompts_do_not_shrink_completed_turn_window(memory_store):
    messages = memory_store[1]
    messages[:] = history(6)
    messages.extend(
        {
            "role": "user",
            "turn_id": f"queued-{i}",
            "content": "继续",
            "createdAt": "2026-01-01 00:00:00.000000",
        }
        for i in range(20)
    )
    view = await short_term.get_session_view("queue", **SCOPE)
    assert len(view["messages"]) == 12
    assert view["messages"][0]["turn_id"] == "turn-0"


@pytest.mark.asyncio
async def test_failed_refresh_keeps_last_good_summary_and_uncovered_messages(
    memory_store, monkeypatch
):
    first = await short_term.get_session_view("failed", **SCOPE)
    memory_store[1].extend(history(8)[-2:])

    def failing_llm(_messages):
        raise RuntimeError("模型暂不可用")

    monkeypatch.setattr(summarizer, "chat", failing_llm)
    second = await short_term.get_session_view("failed", **SCOPE)
    assert second["summary"] == first["summary"]
    assert second["summary_status"] == "failed"
    assert (
        second["summary_source_to_message_id"] == first["summary_source_to_message_id"]
    )
    assert len(second["messages"]) == 14
    assert second["messages"][0]["turn_id"] == "turn-1"


@pytest.mark.asyncio
async def test_reset_excludes_old_history_and_old_inflight_answer(memory_store):
    before = await short_term.get_session_view("reset", **SCOPE)
    assert before["summary"]
    await short_term.reset_session("reset", **SCOPE)
    messages = memory_store[1]
    # 重置前的请求即便之后才结束，也不能与新的用户输入配对。
    messages.append(
        {
            "role": "assistant",
            "turn_id": "turn-0",
            "content": "迟到的旧回复",
            "createdAt": "2099-01-01 00:00:00.000000",
        }
    )
    view = await short_term.get_session_view("reset", **SCOPE)
    assert view["reset_generation"] == 1
    assert view["summary"] is None
    assert view["messages"] == []


@pytest.mark.asyncio
async def test_history_read_failure_is_unavailable_not_empty(memory_store, monkeypatch):
    monkeypatch.setattr(
        chat_store, "load_recent", AsyncMock(side_effect=RuntimeError("读取失败"))
    )
    view = await short_term.get_session_view("unavailable", **SCOPE)
    assert view["source_status"] == "unavailable"


@pytest.mark.asyncio
async def test_summary_commits_after_turn_revision_advances(fake_state_store):
    claim = await chat_store.claim_summary_generation(
        "race",
        **SCOPE,
        source_conversation_revision=0,
        summary_key="summary-1",
    )
    await chat_store.save_conversation_state(
        "race",
        **SCOPE,
        expected_revision=0,
        pending_action={"tool": "create_work_order"},
        idempotency_key="turn-1",
    )
    result = await chat_store.save_summary_result(
        "race",
        **SCOPE,
        expected_revision=0,
        source_conversation_revision=0,
        summary_key="summary-1",
        lease_token=claim["summary_lease"]["token"],
        summary="已确认地块",
        status="ready",
    )
    assert result["summary"] == "已确认地块"
    assert result["conversation_revision"] == 1
    assert result["pending_action"] == {"tool": "create_work_order"}
    assert result["last_write_key"] == "turn-1"
    assert result["summary_lease"] is None


@pytest.mark.asyncio
async def test_expired_lease_can_be_taken_over_and_old_worker_cannot_commit(
    fake_state_store,
):
    first = await chat_store.claim_summary_generation(
        "lease",
        **SCOPE,
        source_conversation_revision=0,
        summary_key="same-range",
    )
    fake_state_store.documents[0]["summaryLease"]["expires_at"] = "2020-01-01T00:00:00Z"
    replacement = await chat_store.claim_summary_generation(
        "lease",
        **SCOPE,
        source_conversation_revision=0,
        summary_key="same-range",
    )
    assert replacement["summary_lease"]["token"] != first["summary_lease"]["token"]
    common = dict(
        conversation_id="lease",
        **SCOPE,
        expected_revision=0,
        source_conversation_revision=0,
        summary_key="same-range",
        status="ready",
    )
    stale = await chat_store.save_summary_result(
        **common,
        lease_token=first["summary_lease"]["token"],
        summary="过时摘要",
    )
    fresh = await chat_store.save_summary_result(
        **common,
        lease_token=replacement["summary_lease"]["token"],
        summary="新摘要",
    )
    assert stale["code"] == "summary_lease_lost"
    assert fresh["summary"] == "新摘要"


@pytest.mark.asyncio
async def test_reset_invalidates_inflight_summary(fake_state_store):
    claim = await chat_store.claim_summary_generation(
        "reset-lease",
        **SCOPE,
        source_conversation_revision=0,
        summary_key="summary",
    )
    await chat_store.reset_conversation_state("reset-lease", **SCOPE)
    rejected = await chat_store.save_summary_result(
        "reset-lease",
        **SCOPE,
        expected_revision=0,
        source_conversation_revision=0,
        summary_key="summary",
        lease_token=claim["summary_lease"]["token"],
        summary="旧代次",
        status="ready",
    )
    assert rejected["code"] == "summary_lease_lost"
    state = await chat_store.get_conversation_state("reset-lease", **SCOPE)
    assert state["summary"] is None


@pytest.mark.asyncio
async def test_summary_timeout_releases_lease_for_retry(memory_store, monkeypatch):
    async def timed_out(*args, **kwargs):
        raise TimeoutError("模型超时")

    with monkeypatch.context() as patch:
        patch.setattr(summarizer.asyncio, "to_thread", timed_out)
        failed = await summarizer.maybe_summarize_async(
            "timeout",
            **SCOPE,
            source_conversation_revision=0,
        )
    state = await chat_store.get_conversation_state("timeout", **SCOPE)
    assert failed.status == "failed"
    assert state["summary_lease"] is None
    ready = await summarizer.maybe_summarize_async(
        "timeout",
        **SCOPE,
        source_conversation_revision=0,
    )
    assert ready.status == "ready"


@pytest.mark.asyncio
async def test_two_workers_reading_same_snapshot_cannot_both_claim(
    fake_state_store, monkeypatch
):
    await chat_store.save_conversation_state("concurrent", **SCOPE)
    original = conversation_state.get_conversation_state
    barrier = asyncio.Event()
    reads = 0

    async def snapshot_before_claim(*args, **kwargs):
        nonlocal reads
        snapshot = await original(*args, **kwargs)
        reads += 1
        if reads == 2:
            barrier.set()
        await barrier.wait()
        return snapshot

    monkeypatch.setattr(
        conversation_state, "get_conversation_state", snapshot_before_claim
    )
    results = await asyncio.gather(
        *[
            chat_store.claim_summary_generation(
                "concurrent",
                **SCOPE,
                source_conversation_revision=1,
                summary_key=key,
            )
            for key in ("worker-a", "worker-b")
        ]
    )
    assert sum(bool(result["ok"]) for result in results) == 1
    assert {result["status"] for result in results} == {"ready", "conflict"}


@pytest.mark.asyncio
async def test_stale_summary_base_cannot_replace_newer_summary(fake_state_store):
    await chat_store.save_conversation_state(
        "stale-base",
        **SCOPE,
        summary="新的有效摘要",
        summary_revision=2,
    )
    result = await chat_store.claim_summary_generation(
        "stale-base",
        **SCOPE,
        source_conversation_revision=1,
        summary_key="old",
        source_summary_revision=1,
    )
    assert result["code"] == "summary_base_revision_conflict"


@pytest.mark.asyncio
async def test_repeated_summary_failures_keep_all_bounded_uncovered_history(
    memory_store, monkeypatch
):
    def failing_llm(_messages):
        raise RuntimeError("不可用")

    monkeypatch.setattr(summarizer, "chat", failing_llm)
    memory_store[1][:] = history(20)
    view = await short_term.get_session_view("backlog", **SCOPE)
    assert len(view["messages"]) == 40
    assert view["messages"][0]["turn_id"] == "turn-0"
