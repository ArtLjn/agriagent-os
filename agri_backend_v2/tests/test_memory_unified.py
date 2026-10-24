"""统一学习回归：事实粒度、事件恢复、原文边界和提交结果。"""

import json
import time
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_personalization import Collection

from agent.domains.harness.memory import learning, tools
from agent.domains.harness.memory.personalization import (
    MemoryCreate,
    MemoryError,
    context_text,
)
from agent.domains.harness.runtime.turn import Turn
from agent.platforms.persistence.mongo import chat_store
from agent.platforms.persistence.mongo import personalization_store as store


@pytest.fixture
def collection(monkeypatch):
    coll = Collection()
    monkeypatch.setattr(store, "collection", lambda: coll)
    return coll


def candidate(slot, text, **changes):
    return learning.Candidate(
        key="food.fruit",
        slot=slot,
        text=text,
        evidence=text,
        category="preference",
        scope="user",
        **changes,
    )


def task(doc, turn="one", observed_at=1, **changes):
    return {
        "user_id": "u",
        "farm_uid": "f",
        "turn_id": turn,
        "conversation_id": "conversation",
        "observed_at": observed_at,
        "generation": doc["memory_generation"],
        "learning_generation": doc["learning_generation"],
        "expected_revision": doc["revision"],
        **changes,
    }


@pytest.mark.asyncio
async def test_partial_correction_preserves_other_fact_and_resets_only_its_evidence(
    collection,
):
    await learning.apply_candidates(
        task(await store.load("u")),
        [candidate("grape", "喜欢葡萄"), candidate("mango", "喜欢芒果")],
    )
    doc = await store.load("u")
    record = doc["memories"][0]
    other = deepcopy(record["atoms"][1])
    result = await learning.apply_candidates(
        task(doc, "two", 2),
        [
            candidate(
                "grape",
                "不喜欢葡萄",
                relation="contradict",
                target_memory_id=record["memory_id"],
                target_slot="grape",
            )
        ],
    )
    updated = (await store.load("u"))["memories"][0]
    assert result["applied_count"] == 1
    assert updated["atoms"][1] == other
    assert updated["atoms"][0]["source_message_ids"] == ["turn:two"]
    assert updated["atoms"][0]["valid_from"] == 2
    assert updated["text"] == "不喜欢葡萄；喜欢芒果"


@pytest.mark.asyncio
async def test_older_unrelated_fact_is_not_discarded_by_topic_timestamp(collection):
    await learning.apply_candidates(
        task(await store.load("u"), observed_at=20), [candidate("grape", "不喜欢葡萄")]
    )
    doc = await store.load("u")
    target = doc["memories"][0]["memory_id"]
    await learning.apply_candidates(
        task(doc, "older", 10),
        [candidate("mango", "喜欢芒果", relation="merge", target_memory_id=target)],
    )
    doc = await store.load("u")
    assert len(doc["memories"][0]["atoms"]) == 2
    result = await learning.apply_candidates(
        task(doc, "stale", 10),
        [
            candidate(
                "grape",
                "喜欢葡萄",
                relation="contradict",
                target_memory_id=target,
                target_slot="grape",
            )
        ],
    )
    assert result["applied_count"] == 0
    assert (await store.load("u"))["memories"][0]["text"].startswith("不喜欢葡萄")


@pytest.mark.asyncio
async def test_delete_erases_atoms_and_prevents_old_task_revival(collection):
    await learning.apply_candidates(
        task(await store.load("u")), [candidate("grape", "喜欢葡萄")]
    )
    doc = await store.load("u")
    pending = task(doc, "pending", 2)
    await store.modify_memory("u", "f", doc["memories"][0]["memory_id"])
    result = await learning.apply_candidates(pending, [candidate("grape", "喜欢葡萄")])
    assert result["reason"] == "control_changed"
    deleted = await store.load("u")
    assert "葡萄" not in str(deleted) and "atoms" not in deleted["memories"][0]


@pytest.mark.asyncio
async def test_recall_filters_unrelated_facts_and_keeps_global_scope(collection):
    await learning.apply_candidates(
        task(await store.load("u")), [candidate("grape", "不喜欢葡萄")]
    )
    doc = await store.load("u")
    assert "不喜欢葡萄" in context_text(doc, "other-farm", query="想吃葡萄")
    assert "不喜欢葡萄" not in context_text(doc, "f", query="查看工单")
    assert "不喜欢葡萄" in context_text(
        doc, "f", query="口味", semantic_ids=[doc["memories"][0]["memory_id"]]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "timeout", "completed"])
async def test_learning_enqueue_does_not_depend_on_assistant_outcome(
    collection, monkeypatch, status
):
    queue = SimpleNamespace(update_one=AsyncMock())
    monkeypatch.setattr(learning, "jobs", lambda: queue)
    turn = Turn(user_id="u", farm_uid="f", user_input="我喜欢葡萄")
    turn.status = status
    assert await learning.enqueue(turn) == "queued"
    assert queue.update_one.call_args.kwargs["upsert"] is True
    first_id = queue.update_one.call_args.args[0]["_id"]
    await learning.enqueue(turn)
    assert queue.update_one.call_args.args[0]["_id"] == first_id


@pytest.mark.asyncio
async def test_relay_acknowledges_only_durable_queue_and_replays_same_message(
    monkeypatch,
):
    message = {
        "_id": "message",
        "userId": "u",
        "conversationId": "c",
        "turnId": "t",
        "content": "喜欢葡萄",
        "memoryLearning": {"farm_uid": "f", "observed_at": 1},
    }
    messages = SimpleNamespace(
        find_one=AsyncMock(return_value=message), update_one=AsyncMock()
    )
    enqueue = AsyncMock(side_effect=["unavailable", "queued"])
    monkeypatch.setattr(chat_store, "get_collection", lambda: messages)
    monkeypatch.setattr(learning, "enqueue", enqueue)
    await learning.relay_observation()
    messages.update_one.assert_not_called()
    await learning.relay_observation()
    assert (
        messages.update_one.call_args.args[1]["$set"]["memoryLearning.status"]
        == "queued"
    )
    assert enqueue.call_args.args[0].turn_id == "t"


@pytest.mark.asyncio
async def test_correction_with_previous_error_is_observation_not_permission_failure(
    collection, memory_assessment_stub
):
    memory = await store.create_memory(
        "u", "f", MemoryCreate(memory_id="fruit", key="fruit", text="喜欢葡萄")
    )
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        preference_statement=True
    )
    turn = Turn(
        user_id="u",
        farm_uid="f",
        user_input="我不喜欢葡萄了",
        memory_snapshot={
            "messages": [{"role": "assistant", "content": "上轮保存失败，请确认"}]
        },
    )
    result = await tools.execute(
        turn,
        {
            "action": "update",
            "memory_id": memory["memory_id"],
            "text": "不喜欢葡萄",
            "evidence": turn.user_input,
        },
        "call",
    )
    assert result["ok"] and result["code"] == tools.OBSERVATION_ONLY_CODE
    assert result["persisted"] is False


def response(payload):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=json.dumps(payload, ensure_ascii=False))
            )
        ]
    )


@pytest.mark.asyncio
async def test_normalization_requires_complete_and_grounded_facts(monkeypatch):
    from agent.platforms.llm import client

    record = {
        "text": "喜欢葡萄和芒果",
        "source_type": "explicit",
        "updated_at": "2026-10-20T00:00:00+00:00",
    }
    create = AsyncMock(
        side_effect=[
            response(
                {
                    "facts": [
                        {"slot": "grape", "text": "喜欢葡萄", "evidence": "喜欢葡萄"}
                    ]
                }
            ),
            response({"equivalent": False}),
        ]
    )
    monkeypatch.setattr(client._async_client.chat.completions, "create", create)
    with pytest.raises(MemoryError, match="完整性"):
        await learning.normalize_record(record)
    assert "atoms" not in record


@pytest.mark.asyncio
async def test_explicit_and_background_use_same_atom_committer(collection, monkeypatch):
    extractor = AsyncMock(return_value=[candidate("grape", "不喜欢葡萄")])
    monkeypatch.setattr(learning, "extract", extractor)
    turn = Turn(user_id="u", farm_uid="f", user_input="记住我不喜欢葡萄")
    result = await learning.remember_explicit(turn, "不喜欢葡萄", "user")
    assert result["applied_count"] == 1
    doc = await store.load("u")
    record = doc["memories"][0]
    assert record["atoms"][0]["source_type"] == "explicit"
    monkeypatch.setattr(
        learning,
        "align_candidates",
        AsyncMock(
            return_value=[
                candidate(
                    "grape",
                    "不喜欢葡萄",
                    relation="reinforce",
                    target_memory_id=record["memory_id"],
                    target_slot="grape",
                )
            ]
        ),
    )
    repeated = await learning.remember_explicit(turn, "不喜欢葡萄", "user")
    assert repeated["reason"] == "already_applied"
    assert (await store.load("u"))["revision"] == doc["revision"]
    result = await learning.apply_candidates(
        task(doc, "later", time.time() + 1),
        [
            candidate(
                "grape",
                "喜欢葡萄",
                target_memory_id=record["memory_id"],
                target_slot="grape",
                relation="contradict",
            )
        ],
    )
    assert result["applied_count"] == 1
    assert (await store.load("u"))["memories"][0]["atoms"][0]["text"] == "喜欢葡萄"


@pytest.mark.asyncio
async def test_bad_evidence_is_retryable_failure_not_partial_success(monkeypatch):
    from agent.platforms.llm import client

    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=response(
                {
                    "candidates": [
                        candidate("grape", "喜欢葡萄").model_dump(),
                        candidate("mango", "喜欢芒果").model_dump(),
                    ]
                }
            )
        ),
    )
    with pytest.raises(MemoryError, match="证据"):
        await learning.extract("我喜欢葡萄芒果")


@pytest.mark.asyncio
async def test_conflicting_values_in_same_extraction_are_not_partially_committed(
    monkeypatch,
):
    from agent.platforms.llm import client

    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=response(
                {
                    "candidates": [
                        candidate("grape", "喜欢葡萄").model_dump(),
                        candidate("grape", "不喜欢葡萄").model_dump(),
                    ]
                }
            )
        ),
    )
    with pytest.raises(MemoryError, match="冲突"):
        await learning.extract("以前喜欢葡萄，现在不喜欢葡萄")


@pytest.mark.asyncio
async def test_explicit_save_promotes_same_turn_background_fact_without_double_evidence(
    collection,
):
    await learning.apply_candidates(
        task(await store.load("u")), [candidate("grape", "喜欢葡萄")]
    )
    doc = await store.load("u")
    target = doc["memories"][0]["memory_id"]
    result = await learning.apply_candidates(
        task(doc, source_type="explicit"),
        [
            candidate(
                "grape",
                "喜欢葡萄",
                relation="reinforce",
                target_memory_id=target,
                target_slot="grape",
            )
        ],
    )
    atom = (await store.load("u"))["memories"][0]["atoms"][0]
    assert result["applied_count"] == 1
    assert atom["source_type"] == "explicit" and atom["evidence_count"] == 1
