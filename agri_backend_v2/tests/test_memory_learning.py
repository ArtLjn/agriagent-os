"""自动学习与语义归并：无需逐条审批，仍遵守来源、并发、删除与用户控制。"""

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_personalization import Collection

from agent.domains.harness.memory import learning
from agent.domains.harness.memory.personalization import (
    MemoryError,
    MemoryPatch,
    context_text,
    new_document,
)
from agent.platforms.persistence.mongo import personalization_store as store


@pytest.fixture
def collection(monkeypatch):
    coll = Collection()
    monkeypatch.setattr(store, "collection", lambda: coll)
    return coll


def task(doc, turn="one", observed_at=1):
    return {
        "user_id": "u",
        "farm_uid": "f",
        "turn_id": turn,
        "conversation_id": "same-session",
        "generation": doc["memory_generation"],
        "learning_generation": doc["learning_generation"],
        "expected_revision": doc["revision"],
        "observed_at": observed_at,
    }


def fruit(**changes):
    return learning.Candidate.model_validate(
        {
            "key": "food.fruit",
            "slot": "watermelon",
            "text": "喜欢西瓜",
            "evidence": "我喜欢西瓜",
            "category": "preference",
            **changes,
        }
    )


@pytest.mark.asyncio
async def test_default_learning_respects_explicit_disable_and_does_not_write_on_read(
    collection,
):
    assert (await store.load("u"))["settings"]["auto_learn_enabled"] is True
    assert not collection.docs
    old = new_document(store.owner_key("u"))
    old["settings"]["auto_learn_enabled"] = False
    await collection.insert_one(old)
    assert (await store.load("u"))["settings"]["auto_learn_enabled"] is True
    # 兼容旧默认值仅是读取投影，不能把读操作伪装成已迁移存储。
    assert collection.docs[old["_id"]]["settings"]["auto_learn_enabled"] is False
    old["field_sources"]["auto_learn_enabled"] = "explicit"
    collection.docs[old["_id"]] = old
    doc = await store.load("u")
    assert doc["settings"]["auto_learn_enabled"] is False
    await learning.apply_candidates(task(doc), [fruit()])
    assert not (await store.load("u"))["memories"]


@pytest.mark.asyncio
async def test_first_observation_is_active_and_retries_do_not_duplicate(collection):
    doc = await store.load("u")
    await learning.apply_candidates(task(doc), [fruit()])
    doc = await store.load("u")
    await learning.apply_candidates(task(doc), [fruit()])
    result = await store.load("u")
    assert result["revision"] == doc["revision"]
    assert len(result["memories"]) == 1
    memory = result["memories"][0]
    assert memory["status"] == "active" and memory["category"] == "preference"
    assert memory["evidence_count"] == 1 and memory["expires_at"] is None
    assert "喜欢西瓜" in context_text(result, "f")
    assert "喜欢西瓜" not in context_text(result, "other-farm")


@pytest.mark.asyncio
async def test_complements_merge_and_correction_replaces_only_conflicting_detail(
    collection,
):
    await learning.apply_candidates(task(await store.load("u")), [fruit()])
    doc = await store.load("u")
    memory_id = doc["memories"][0]["memory_id"]
    await learning.apply_candidates(
        task(doc, "two", 2),
        [
            fruit(
                text="喜欢草莓",
                slot="strawberry",
                evidence="也喜欢草莓",
                relation="merge",
                target_memory_id=memory_id,
            )
        ],
    )
    doc = await store.load("u")
    assert (
        len(doc["memories"]) == 1 and doc["memories"][0]["text"] == "喜欢西瓜；喜欢草莓"
    )
    await learning.apply_candidates(
        task(doc, "three", 3),
        [
            fruit(
                text="不再喜欢西瓜",
                evidence="现在不喜欢西瓜了",
                relation="contradict",
                target_memory_id=memory_id,
                target_slot="watermelon",
            )
        ],
    )
    doc = await store.load("u")
    assert len(doc["memories"]) == 1
    record = doc["memories"][0]
    assert record["status"] == "active" and record["text"] == "不再喜欢西瓜；喜欢草莓"
    assert set(record["source_message_ids"]) == {"turn:two", "turn:three"}
    assert record["atoms"][0]["evidence_count"] == 1
    # 任务晚到也不能覆盖最新纠正。
    await learning.apply_candidates(
        task(doc, "late", 1.5),
        [
            fruit(
                relation="contradict",
                target_memory_id=memory_id,
                target_slot="watermelon",
            )
        ],
    )
    assert (await store.load("u"))["revision"] == doc["revision"]


@pytest.mark.asyncio
async def test_changed_snapshot_retries_instead_of_losing_concurrent_fact(collection):
    doc = await store.load("u")
    pending = task(doc, "stale")
    await learning.apply_candidates(task(doc), [fruit()])
    with pytest.raises(MemoryError, match="重新归并"):
        await learning.apply_candidates(pending, [fruit(text="喜欢葡萄")])
    assert (await store.load("u"))["memories"][0]["text"] == "喜欢西瓜"


@pytest.mark.asyncio
async def test_same_key_without_semantic_relation_does_not_drop_distinct_facts(
    collection,
):
    await learning.apply_candidates(
        task(await store.load("u")),
        [fruit(), fruit(key="work.crop", slot="tomato", text="常种番茄")],
    )
    records = (await store.load("u"))["memories"]
    assert {m["text"] for m in records} == {"喜欢西瓜", "常种番茄"}


@pytest.mark.asyncio
async def test_deleted_or_user_edited_memory_cannot_be_learned_back(collection):
    await learning.apply_candidates(task(await store.load("u")), [fruit()])
    doc = await store.load("u")
    record = doc["memories"][0]
    await store.modify_memory(
        "u",
        "f",
        record["memory_id"],
        MemoryPatch(
            expected_revision=record["revision"],
            text="喜欢芒果",
        ),
    )
    doc = await store.load("u")
    await learning.apply_candidates(
        {
            **task(doc, "two", 2),
            "normalized_atoms": {
                record["memory_id"]: [
                    {
                        "slot": "mango",
                        "text": "喜欢芒果",
                        "source_type": "explicit",
                        "revision": 1,
                        "updated_at": doc["memories"][0]["updated_at"],
                    }
                ]
            },
        },
        [
            fruit(
                relation="contradict",
                target_memory_id=record["memory_id"],
                target_slot="mango",
            )
        ],
    )
    assert (await store.load("u"))["memories"][0]["text"] == "喜欢芒果"
    pending = task(await store.load("u"), "pending", 3)
    await store.modify_memory("u", "f", record["memory_id"])
    await learning.apply_candidates(pending, [fruit()])
    doc = await store.load("u")
    await learning.apply_candidates(task(doc, "new", 4), [fruit()])
    doc = await store.load("u")
    assert doc["memories"][0]["status"] == "deleted"
    assert "芒果" not in str(doc) and "西瓜" not in str(doc)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"durability": "temporary"},
        {"durability": "uncertain"},
        {"durability": "sensitive"},
        {"evidence": "伪造原文"},
        {"merged_text": "密码=secret123"},
        {
            "relation": "merge",
            "target_memory_id": "other-owner",
            "merged_text": "喜欢葡萄",
        },
    ],
)
async def test_unsupported_or_unsafe_observations_are_not_saved(collection, changes):
    doc = await store.load("u")
    await learning.apply_candidates(
        {**task(doc), "text": "我喜欢西瓜"}, [fruit(**changes)]
    )
    assert not (await store.load("u"))["memories"]


@pytest.mark.asyncio
async def test_merge_prefers_category_even_when_related_memory_is_older(monkeypatch):
    from agent.platforms.llm import client

    existing = [
        {"memory_id": str(i), "category": "work", "text": "工作习惯", "key": str(i)}
        for i in range(35)
    ]
    existing.append(
        {
            "memory_id": "fruit",
            "category": "preference",
            "text": "喜欢西瓜",
            "key": "old.fruit",
            "atoms": [{"slot": "watermelon", "text": "喜欢西瓜"}],
        }
    )
    response = {
        "alignments": [
            {
                "candidate_index": 0,
                "target_memory_id": "fruit",
                "relation": "merge",
                "merged_text": None,
            }
        ]
    }
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=f"```json\n{json.dumps(response)}\n```"
                    )
                )
            ]
        )
    )
    monkeypatch.setattr(client._async_client.chat.completions, "create", create)
    result = await learning.align_candidates([fruit(text="喜欢葡萄")], existing)
    payload = json.loads(create.call_args.kwargs["messages"][-1]["content"])
    assert payload["existing_memories"][0]["memory_id"] == "fruit"
    assert (
        len(payload["existing_memories"]) == learning.memory_runtime.review_memory_limit
    )
    assert result[0].target_memory_id == "fruit" and result[0].merged_text is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "alignments",
    [
        [{"candidate_index": 0, "target_memory_id": "fruit", "relation": "contradict"}],
        [
            {
                "candidate_index": 0,
                "target_memory_id": "unknown",
                "relation": "reinforce",
            }
        ],
        [],
    ],
)
async def test_invalid_alignment_does_not_silently_overwrite(monkeypatch, alignments):
    from agent.platforms.llm import client

    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps({"alignments": alignments})
                        )
                    )
                ]
            )
        ),
    )
    with pytest.raises(ValueError, match="memory_alignment"):
        await learning.align_candidates(
            [fruit()],
            [
                {
                    "memory_id": "fruit",
                    "key": "food.fruit",
                    "text": "喜欢西瓜",
                    "atoms": [{"slot": "watermelon", "text": "喜欢西瓜"}],
                }
            ],
        )


@pytest.mark.asyncio
async def test_extraction_cannot_supply_a_merged_text_before_alignment(monkeypatch):
    from agent.platforms.llm import client

    payload = {"candidates": [fruit(merged_text="模型虚构内容").model_dump()]}
    monkeypatch.setattr(learning, "verify_extraction", AsyncMock())
    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(payload))
                    )
                ]
            )
        ),
    )
    result = await learning.extract("我喜欢西瓜")
    assert result[0].merged_text is None and result[0].text == "喜欢西瓜"


@pytest.mark.asyncio
@pytest.mark.parametrize("consistent", [True, False])
async def test_multiple_candidates_cannot_lose_each_others_merge(
    monkeypatch, collection, consistent
):
    from agent.platforms.llm import client

    await learning.apply_candidates(task(await store.load("u")), [fruit()])
    doc = await store.load("u")
    record = doc["memories"][0]
    merged = "喜欢西瓜；喜欢草莓；喜欢葡萄"
    alignments = [
        {
            "candidate_index": i,
            "target_memory_id": record["memory_id"],
            "relation": "merge",
            "merged_text": None if consistent else "只喜欢葡萄",
        }
        for i in range(2)
    ]
    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=json.dumps({"alignments": alignments})
                        )
                    )
                ]
            )
        ),
    )
    candidates = [
        fruit(slot="strawberry", text="喜欢草莓"),
        fruit(slot="grape", text="喜欢葡萄"),
    ]
    if not consistent:
        with pytest.raises(ValueError, match="whole_text_forbidden"):
            await learning.align_candidates(candidates, [record])
        return
    aligned = await learning.align_candidates(candidates, [record])
    await learning.apply_candidates(task(doc, "two", 2), aligned)
    records = (await store.load("u"))["memories"]
    assert len(records) == 1 and records[0]["text"] == merged
    assert records[0]["evidence_count"] == 2


@pytest.mark.asyncio
async def test_category_api_filters_and_legacy_records_remain_readable(collection):
    from agent.api.personalization import list_memories

    await learning.apply_candidates(
        task(await store.load("u")),
        [fruit(), fruit(key="work", text="清晨巡田", category="work", kind="habit")],
    )
    result = await list_memories(
        {"user_id": "u", "farm_uid": "f"}, page=1, page_size=20, category="preference"
    )
    assert result["total"] == 1 and result["items"][0]["category"] == "preference"
    assert not (
        await list_memories(
            {"user_id": "another", "farm_uid": "f"},
            page=1,
            page_size=20,
            category="preference",
        )
    )["items"]


@pytest.mark.skipif(
    os.getenv("AGENT_ROUTING_LIVE") != "1", reason="仅显式开启真实模型回放"
)
@pytest.mark.asyncio
async def test_live_auto_learning_consolidates_fruit_without_confirmation(collection):
    for index, text in enumerate(
        [
            "我一直喜欢吃西瓜",
            "我也一直喜欢吃草莓和葡萄",
            "我现在不喜欢西瓜了，草莓和葡萄还是喜欢的",
        ],
        1,
    ):
        doc = await store.load("u")
        candidates = await learning.extract(text, doc["memories"])
        assert candidates, text
        await learning.apply_candidates(
            {**task(doc, str(index), index), "text": text}, candidates
        )
    records = (await store.load("u"))["memories"]
    assert len(records) == 1, json.dumps(records, ensure_ascii=False)
    assert records[0]["status"] == "active"
    assert records[0]["category"] == "preference"
    assert all(word in records[0]["text"] for word in ["草莓", "葡萄"]), records
    assert "不" in records[0]["text"] or "西瓜" not in records[0]["text"]


@pytest.mark.skipif(
    os.getenv("AGENT_ROUTING_LIVE") != "1", reason="仅显式开启真实模型回放"
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "这次请用表格回答就好",
        "帮我翻译：小王喜欢西瓜",
        "明天提醒我打药",
        "上次系统说保存失败了，请先回复收到。",
    ],
)
async def test_live_learning_does_not_turn_temporary_tasks_into_profile(text):
    assert await learning.extract(text) == []


@pytest.mark.skipif(
    os.getenv("AGENT_ROUTING_LIVE") != "1", reason="仅显式开启真实模型回放"
)
@pytest.mark.asyncio
async def test_live_plain_fruit_preference_does_not_require_memory_request(collection):
    text = "我喜欢吃西瓜芒果葡萄草莓"
    doc = await store.load("u")
    candidates = await learning.extract(text)
    assert candidates and all(c.category == "preference" for c in candidates)
    await learning.apply_candidates({**task(doc), "text": text}, candidates)
    records = (await store.load("u"))["memories"]
    assert records and all(m["status"] == "active" for m in records)
    assert all(
        word in " ".join(m["text"] for m in records)
        for word in ["西瓜", "芒果", "葡萄", "草莓"]
    )
