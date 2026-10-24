"""规模、冲突和最终预算验收；真实 Mongo 压力数据只进入随机独立数据库。"""

import asyncio
import json
import os
import time
import uuid
from copy import deepcopy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from test_memory_unified import candidate, task
from test_personalization import Collection

from agent.config import memory_runtime, settings
from agent.domains.harness.context import budget, tokenizer
from agent.domains.harness.memory import learning
from agent.domains.harness.memory.facts import project_facts
from agent.domains.harness.memory.personalization import (
    MemoryError,
    context_text,
    new_document,
)
from agent.platforms.persistence.mongo import memory_records
from agent.platforms.persistence.mongo import personalization_store as store


@pytest.fixture
def inline(monkeypatch):
    coll = Collection()
    monkeypatch.setattr(store, "collection", lambda: coll)
    return coll


@pytest.mark.asyncio
async def test_ambiguous_same_turn_conflict_is_not_truth_and_can_be_resolved(inline):
    await learning.apply_candidates(
        task(await store.load("u")),
        [candidate("grape", "喜欢葡萄"), candidate("grape", "不喜欢葡萄")],
    )
    doc = await store.load("u")
    record = doc["memories"][0]
    atom = record["atoms"][0]
    assert atom["state"] == "conflicted"
    assert {a["text"] for a in atom["alternatives"]} == {"喜欢葡萄", "不喜欢葡萄"}
    projected = project_facts(record, "葡萄")
    assert projected[0]["state"] == "conflicted"
    await learning.apply_candidates(
        task(doc, "clarification", 3),
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
    final = (await store.load("u"))["memories"][0]["atoms"][0]
    assert final["state"] == "active" and final["text"] == "不喜欢葡萄"
    assert "alternatives" not in final


@pytest.mark.asyncio
async def test_historical_statement_and_other_condition_cannot_replace_current(inline):
    await learning.apply_candidates(
        task(await store.load("u")),
        [candidate("grape", "在星河项目中不喜欢葡萄", conditions=["星河项目"])],
    )
    doc = await store.load("u")
    record = doc["memories"][0]
    change = {
        "relation": "contradict",
        "target_memory_id": record["memory_id"],
        "target_slot": "grape",
    }
    await learning.apply_candidates(
        task(doc, "old-story", 3),
        [
            candidate(
                "grape",
                "去年在星河项目中喜欢葡萄",
                temporal_scope="historical",
                time_evidence="去年",
                conditions=["星河项目"],
                **change,
            )
        ],
    )
    doc = await store.load("u")
    await learning.apply_candidates(
        task(doc, "other-place", 4),
        [candidate("grape", "在银月项目中喜欢葡萄", conditions=["银月项目"], **change)],
    )
    record = (await store.load("u"))["memories"][0]
    assert len(record["atoms"]) == 3
    assert record["atoms"][0]["text"] == "在星河项目中不喜欢葡萄"
    assert "去年" not in str(project_facts(record, "当前项目偏好"))
    assert "去年" in str(project_facts(record, "去年喜欢什么"))
    await store.modify_memory("u", "f", record["memory_id"])
    assert "葡萄" not in str(await store.load("u"))


@pytest.mark.asyncio
async def test_partial_inline_update_does_not_remove_unloaded_memories(inline):
    await learning.apply_candidates(
        task(await store.load("u")), [candidate("grape", "喜欢葡萄")]
    )
    doc = await store.load("u")
    other = candidate("blue", "喜欢蓝色").model_copy(update={"key": "color"})
    await learning.apply_candidates(task(doc, "two", 2), [other])
    records = (await store.load("u"))["memories"]
    await store.modify_memory("u", "f", records[0]["memory_id"])
    assert (await store.load("u"))["memories"][1] == records[1]


@pytest.mark.parametrize("size", [1000, 10000, 100000])
def test_final_request_budget_is_bounded_with_large_tool_results(size, monkeypatch):
    monkeypatch.setenv("CONTEXT__MODEL_CONTEXT_TOKENS", "9000")
    messages = [
        {"role": "system", "content": "保留业务权限与确认约束"},
        {"role": "user", "content": "<user-personalization>" + "无关历史" * size},
        {"role": "user", "content": "查葡萄，仅查询不能修改"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "search", "arguments": "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-1",
            "content": json.dumps({"success": True, "data": "长结果" * size}),
        },
        {"role": "system", "content": "<system-reminder>再次提醒"},
    ]
    original = deepcopy(messages)
    result, usage = budget.prepare_request(messages)
    assert usage.used + usage.response_reserve + usage.safety_margin <= usage.total
    assert messages == original
    assert any(m.get("tool_call_id") == "call-1" for m in result)
    assert any(m.get("tool_calls") for m in result)
    assert "仅查询不能修改" in str(result)
    assert "tool_result_omitted_for_budget" in str(result)


@pytest.mark.asyncio
async def test_required_context_never_reaches_provider_when_over_budget(monkeypatch):
    from agent.platforms.llm import client

    monkeypatch.setenv("CONTEXT__MODEL_CONTEXT_TOKENS", "9000")
    create = AsyncMock()
    monkeypatch.setattr(client._async_client.chat.completions, "create", create)
    with pytest.raises(budget.ContextBudgetError) as caught:
        await client.bounded_completion(
            messages=[{"role": "user", "content": "不能截断的证据" * 10000}],
            max_tokens=1000,
        )
    assert caught.value.code == "context_budget_exceeded"
    create.assert_not_called()


def test_multilingual_and_tool_schema_are_counted_conservatively():
    text = "汉字👩‍🌾 العربية 日本語 12345"
    assert tokenizer.count_tokens(text) == len(text.encode())
    tools = [
        {"type": "function", "function": {"name": "查询", "description": text * 100}}
    ]
    usage = tokenizer.compute_usage([{"role": "user", "content": text}], tools=tools)
    assert (
        usage.tool_schema_tokens
        >= len(json.dumps(tools, ensure_ascii=False).encode()) - 10
    )


@pytest_asyncio.fixture
async def isolated_mongo(monkeypatch):
    if os.getenv("AGENT_MEMORY_STRESS") != "1":
        pytest.skip("仅显式开启真实 Mongo 压力验收")
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(
        settings.mongodb.uri, tls=settings.mongodb.tls, serverSelectionTimeoutMS=3000
    )
    name = "memory_scale_qa_" + uuid.uuid4().hex
    root = client[name]["preferences"]
    monkeypatch.setattr(store, "collection", lambda: root)
    try:
        yield root
    finally:
        assert name.startswith("memory_scale_qa_")
        await client.drop_database(name)
        assert name not in await client.list_database_names()
        client.close()


def record(index):
    return {
        "memory_id": f"memory-{index}",
        "revision": 1,
        "key": f"project-{index}",
        "text": f"在项目编号{index}中喜欢颜色{index}",
        "conditions": [],
        "scope": "user",
        "farm_uid": None,
        "source_type": "inferred",
        "kind": "preference",
        "status": "active",
        "category": "preference",
        "created_at": "2026-10-24T00:00:00+00:00",
        "updated_at": "2026-10-24T00:00:00+00:00",
        "expires_at": None,
        "atoms": [
            {
                "slot": f"project-{index}.color",
                "text": f"项目{index}喜欢颜色{index}",
                "revision": 1,
                "source_type": "inferred",
                "updated_at": "2026-10-24T00:00:00+00:00",
            }
        ],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("size", [1000, 3000, 10000])
async def test_real_mongo_scale_cas_delete_and_bounded_retrieval(isolated_mongo, size):
    doc = new_document(store.owner_key("u"))
    doc["memories"] = [record(i) for i in range(size)]
    started = time.perf_counter()
    await store.save(doc, 0)
    save_seconds = time.perf_counter() - started
    head = await isolated_mongo.find_one({"_id": doc["_id"]})
    assert "memories" not in head and len(head["memory_refs"]) == size
    assert head["active_memory_count"] == size
    timings = []

    async def recall(index):
        start = time.perf_counter()
        found = await store.load(
            "u",
            query=f"项目编号{index}",
            farm_uid="f",
            slots=[f"project-{index}.color"] if index % 2 else [],
        )
        timings.append(time.perf_counter() - start)
        assert len(found["memories"]) <= memory_records.RETRIEVAL_LIMIT
        assert found["memories"][0]["memory_id"] == f"memory-{index}"
        assert (
            tokenizer.count_tokens(context_text(found, "f", query=f"项目编号{index}"))
            <= memory_runtime.context_tokens
        )

    # 串行基线与并发读取都检查目标召回，不能只验证返回了 HTTP 200。
    await recall(size - 1)
    await asyncio.gather(*(recall(i * (size // 12)) for i in range(12)))
    partial_a = await store.load("u", memory_ids=["memory-0"])
    partial_b = await store.load("u", memory_ids=["memory-1"])
    old_ref = partial_a["memory_refs"]["memory-0"]
    partial_a["memories"][0].update(text="更正后的独立事实", revision=2)
    await store.save(partial_a, partial_a["revision"])
    with pytest.raises(MemoryError, match="变化"):
        await store.save(partial_b, partial_b["revision"])
    collection = isolated_mongo.database[memory_records.COLLECTION]
    assert await collection.find_one({"_id": old_ref}) is None
    assert (await store.load("u", memory_ids=[f"memory-{size - 1}"]))["memories"][0][
        "text"
    ] == record(size - 1)["text"]
    await store.modify_memory("u", "f", "memory-0")
    tombstone = (await store.load("u", memory_ids=["memory-0"]))["memories"][0]
    assert (
        tombstone["status"] == "deleted"
        and not tombstone["text"]
        and "atoms" not in tombstone
    )
    assert (
        await collection.count_documents(
            {"owner": doc["_id"], "record.text": "更正后的独立事实"}
        )
        == 0
    )
    assert not (await store.load("other", query="项目", farm_uid="f"))["memories"]
    p95 = sorted(timings)[int((len(timings) - 1) * 0.95)]
    assert p95 < 5, f"并发召回 P95 超过压力验收上限: {p95}"
    report = {
        "size": size,
        "save_seconds": save_seconds,
        "recall_p95_seconds": p95,
        "max_candidates": memory_records.RETRIEVAL_LIMIT,
        "recall_hits": len(timings),
        "cleanup": "fixture_finally",
    }
    await asyncio.to_thread(append_benchmark, report)


def append_benchmark(report):
    with Path("/tmp/memory-scale-benchmark.jsonl").open("a") as output:
        output.write(json.dumps(report) + "\n")


@pytest.mark.asyncio
async def test_unpublished_copy_is_not_recalled_or_deleted_before_cas_is_impossible(
    isolated_mongo,
):
    doc = new_document(store.owner_key("u"))
    doc["memories"] = [record(i) for i in range(201)]
    await store.save(doc, 0)
    coll = isolated_mongo.database[memory_records.COLLECTION]
    original = await coll.find_one({"memory_id": "memory-0"})
    orphan = {
        **deepcopy(original),
        "_id": "unpublished",
        "base_revision": 1,
        "created_at": 0,
    }
    orphan["record"]["text"] = "绝不能召回的未发布版本"
    orphan["terms"] = ["未发布"]
    await coll.insert_one(orphan)
    assert not (await store.load("u", query="未发布", farm_uid="f"))["memories"]
    await memory_records.collect_orphans(isolated_mongo)
    assert await coll.find_one({"_id": "unpublished"}) is not None
    head = await store.load("u", memory_ids=[])
    await store.save(head, head["revision"])
    await memory_records.collect_orphans(isolated_mongo)
    assert await coll.find_one({"_id": "unpublished"}) is None
    assert (await store.load("u", memory_ids=["memory-0"]))["memories"][0][
        "text"
    ] == original["record"]["text"]
    expired = await store.load("u", memory_ids=["memory-0"])
    expired["memories"][0]["expires_at"] = "2020-01-01T00:00:00+00:00"
    await store.save(expired, expired["revision"])
    expired_page = await store.page_memories(
        "u", "f", page=1, page_size=20, status="expired"
    )
    assert (
        expired_page["total"] == 1 and expired_page["items"][0]["status"] == "expired"
    )
    page = await store.page_memories("u", "f", page=2, page_size=20, status="active")
    assert page["total"] == 200 and len(page["items"]) == 20


@pytest.mark.asyncio
async def test_exact_slot_survives_large_alignment_window(monkeypatch):
    from types import SimpleNamespace

    from agent.platforms.llm import client

    existing = [record(i) for i in range(10000)]
    captured = []

    async def complete(**request):
        payload = json.loads(request["messages"][-1]["content"])
        captured.extend(payload["existing_memories"])
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "alignments": [
                                    {
                                        "candidate_index": 0,
                                        "target_memory_id": "memory-5",
                                        "target_slot": "project-5.color",
                                        "relation": "contradict",
                                    }
                                ]
                            }
                        )
                    )
                )
            ]
        )

    monkeypatch.setattr(client._async_client.chat.completions, "create", complete)
    observation = candidate("project-5.color", "这个项目改用蓝色").model_copy(
        update={"key": "新措辞"}
    )
    result = await learning.align_candidates([observation], existing)
    assert result[0].target_memory_id == "memory-5"
    assert len(captured) <= memory_runtime.review_memory_limit
    assert (
        len(json.dumps(captured, ensure_ascii=False).encode())
        < memory_runtime.review_bytes + 100
    )


@pytest.mark.asyncio
async def test_legacy_missing_conditions_does_not_fork_a_correction(inline):
    await learning.apply_candidates(
        task(await store.load("u")), [candidate("sky.color", "星河项目喜欢蓝色")]
    )
    doc = await store.load("u")
    old = doc["memories"][0]
    await learning.apply_candidates(
        task(doc, "correction", 3),
        [
            candidate(
                "sky.color",
                "星河项目不喜欢蓝色",
                conditions=["星河项目"],
                relation="contradict",
                target_memory_id=old["memory_id"],
                target_slot="sky.color",
            )
        ],
    )
    atoms = (await store.load("u"))["memories"][0]["atoms"]
    assert len(atoms) == 1 and atoms[0]["text"] == "星河项目不喜欢蓝色"
    assert atoms[0]["conditions"] == ["星河项目"]


@pytest.mark.asyncio
async def test_historical_alignment_can_anchor_current_slot_without_overwrite(
    inline, monkeypatch
):
    from types import SimpleNamespace

    from agent.platforms.llm import client

    await learning.apply_candidates(
        task(await store.load("u")), [candidate("grape", "现在不喜欢葡萄")]
    )
    doc = await store.load("u")
    target = doc["memories"][0]
    response = {
        "alignments": [
            {
                "candidate_index": 0,
                "target_memory_id": target["memory_id"],
                "target_slot": "grape",
                "relation": "merge",
            }
        ]
    }
    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(response))
                    )
                ]
            )
        ),
    )
    candidates = await learning.align_candidates(
        [
            candidate(
                "grape",
                "去年喜欢葡萄",
                temporal_scope="historical",
                time_evidence="去年",
            )
        ],
        doc["memories"],
    )
    await learning.apply_candidates(task(doc, "history", 3), candidates)
    final = (await store.load("u"))["memories"][0]
    assert len(final["atoms"]) == 2
    assert [f["text"] for f in project_facts(final, "现在")] == ["现在不喜欢葡萄"]


def test_user_supplied_optional_tag_is_never_dropped(monkeypatch):
    monkeypatch.setenv("CONTEXT__MODEL_CONTEXT_TOKENS", "9000")
    with pytest.raises(budget.ContextBudgetError):
        budget.prepare_request(
            [{"role": "user", "content": "<session-summary>" + "用户证据" * 10000}]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("equivalent", [True, False])
async def test_condition_alignment_distinguishes_paraphrase_from_other_scene(
    inline, monkeypatch, equivalent
):
    from types import SimpleNamespace

    from agent.platforms.llm import client

    await learning.apply_candidates(
        task(await store.load("u")),
        [candidate("milk", "喝拿铁时喜欢燕麦奶", conditions=["喝拿铁"])],
    )
    doc = await store.load("u")
    record = doc["memories"][0]
    response = {
        "alignments": [
            {
                "candidate_index": 0,
                "target_memory_id": record["memory_id"],
                "target_slot": "milk",
                "relation": "contradict",
                "conditions_equivalent": equivalent,
            }
        ]
    }
    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(response))
                    )
                ]
            )
        ),
    )
    scene = "喝拿铁时" if equivalent else "喝豆浆时"
    candidates = await learning.align_candidates(
        [candidate("milk", f"{scene}喜欢豆奶", conditions=[scene])], doc["memories"]
    )
    await learning.apply_candidates(task(doc, "correction", 3), candidates)
    atoms = (await store.load("u"))["memories"][0]["atoms"]
    assert len(atoms) == (1 if equivalent else 2)
    if equivalent:
        assert atoms[0]["conditions"] == ["喝拿铁"]
        assert "豆奶" in atoms[0]["text"]
        assert "燕麦奶" in atoms[0]["history"][0]["text"]
    else:
        assert "燕麦奶" in atoms[0]["text"]
        assert atoms[1]["conditions"] == [scene]


@pytest.mark.parametrize("name", ["MEMORY_REVIEW_BYTES", "MEMORY_CONTEXT_TOKENS"])
def test_memory_budget_environment_rejects_invalid_limits(name, monkeypatch):
    from agent.config import MemoryRuntimeCfg

    monkeypatch.setenv(name, "0")
    with pytest.raises(ValueError, match="memory_config_must_be_positive"):
        MemoryRuntimeCfg()


@pytest.mark.parametrize(
    "reply",
    [
        "根据已保存的记忆，你喝拿铁不加糖。",
        "从已经保存的长期记忆中读取：偏好燕麦奶。",
        "根据我目前能读取到的已保存记忆，没有找到相关记录。",
        "根据我目前能读取到的已保存的记忆，没有找到相关记录。",
    ],
)
def test_recalling_saved_memories_is_not_a_new_write_claim(reply):
    from agent.domains.harness.runtime.verify import (
        claims_write_completion,
        looks_like_write_request,
    )

    assert not claims_write_completion(reply)
    assert claims_write_completion(reply + "我已经为你创建工单。")
    assert claims_write_completion("根据你的要求，我已保存记忆。")
    assert claims_write_completion("我已保存的记忆已更新。")
    assert not looks_like_write_request("只根据已保存的记忆回答，不要猜。")
    assert looks_like_write_request("请删除已保存的长期记忆。")


def test_random_life_samples_are_natural_unique_and_reproducible():
    from memory_life_samples import life_samples

    rows = life_samples()
    assert len(rows) == len({r["text"] for r in rows}) == 3000
    assert rows == life_samples()
    assert rows != life_samples(seed=42)
    assert len({r["key"].split(".")[0] for r in rows}) >= 10
    assert all("回归样本" not in r["text"] and len(r["text"]) <= 500 for r in rows)
    assert sum(r["temporal_scope"] == "historical" for r in rows) == 300


@pytest.mark.asyncio
async def test_life_memory_reading_budget_and_cached_concurrency(
    isolated_mongo, monkeypatch
):
    """真实 3000 条生活记忆存储压测；阅读器替身只用于测确定性的预算与缓存开销。"""
    from memory_life_samples import life_samples

    from agent.domains.harness.memory import inference, long_term

    doc = new_document(store.owner_key("u"))
    doc["memories"] = []
    for index, sample in enumerate(life_samples()):
        row = record(index)
        row.update(
            key=sample["key"], text=sample["text"], conditions=sample["conditions"]
        )
        row["atoms"] = [
            {
                "slot": str(index),
                "text": sample["text"],
                "conditions": sample["conditions"],
                "state": "active",
                "temporal_scope": sample["temporal_scope"],
            }
        ]
        doc["memories"].append(row)
    await store.save(doc, 0)
    counts = []

    async def read(query, facts, history, **kwargs):
        counts.append(len(facts))
        return inference.ContextReading(
            selections=[
                inference.ContextSelection(
                    ref=f["ref"],
                    use="recommend",
                    applicability="conditional",
                    aspect=str(f["ref"]),
                )
                for f in facts[:4]
            ]
        )

    monkeypatch.setattr(memory_runtime, "context_mode", "read")
    reader = AsyncMock(side_effect=read)
    monkeypatch.setattr(inference, "read_context", reader)
    monkeypatch.setattr(
        "agent.platforms.persistence.memory_index.retrieve", AsyncMock(return_value=[])
    )
    first = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="在家休闲"
    )
    assert first["personalization_diagnostics"]["status"] == "ready", first
    times = []

    async def reuse():
        start = time.monotonic()
        result = await long_term.get_personalization_context(
            user_id="u", farm_uid="f", query="在家休闲", previous=first
        )
        times.append(time.monotonic() - start)
        assert result["personalization_diagnostics"]["cached"]
        assert result["personalization_diagnostics"]["injected_count"] > 0
        assert (
            tokenizer.count_tokens(result["personalization"])
            <= memory_runtime.context_tokens
        )

    await asyncio.gather(*(reuse() for _ in range(12)))
    assert reader.await_count == 1 and max(counts) <= memory_runtime.context_fact_limit
    p95 = sorted(times)[int((len(times) - 1) * 0.95)]
    assert p95 < 5
    append_benchmark(
        {
            "kind": "reading_cache",
            "size": 3000,
            "cached_concurrency": 12,
            "cached_p95_seconds": p95,
            "candidate_count": max(counts),
            "model": "stub_not_quality_evaluation",
            "cleanup": "fixture_finally",
        }
    )


@pytest.mark.asyncio
async def test_supplementary_coverage_does_not_only_return_rare_distractions(
    isolated_mongo,
):
    """罕见的舒适鞋不能让常见居家事实完全失去进入阅读阶段的机会。"""
    doc = new_document(store.owner_key("u"))
    doc["memories"] = [record(i) for i in range(220)]
    for row in doc["memories"]:
        row.update(text="在家休闲时喜欢听轻音乐", key="休闲.居家")
        row["atoms"][0]["text"] = row["text"]
    doc["memories"][0]["text"] = "登山时喜欢舒服的鞋"
    doc["memories"][0]["atoms"][0]["text"] = "登山时喜欢舒服的鞋"
    await store.save(doc, 0)
    focused = await store.load("u", farm_uid="f", query="舒服在家休闲")
    assert len(focused["memories"]) == 1
    broad = await store.load("u", farm_uid="f", query="舒服在家休闲", diversify=True)
    assert len(broad["memories"]) <= memory_records.RETRIEVAL_LIMIT
    assert any("轻音乐" in m["text"] for m in broad["memories"])
    assert not (
        await store.load("another", farm_uid="f", query="在家", diversify=True)
    )["memories"]
