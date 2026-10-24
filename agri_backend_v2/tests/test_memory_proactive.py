"""主动记忆的检索、隔离、故障和真实语义服务验收，不依赖用户说记忆触发词。"""

import asyncio
import os
import time
import uuid
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from test_personalization import Collection

from agent.config import memory_runtime
from agent.domains.harness.memory import inference, long_term
from agent.domains.harness.memory import tools as memory_tools
from agent.domains.harness.memory.personalization import (
    MemoryCreate,
    SettingsPatch,
    answer_context,
    new_document,
    rank_context_records,
)
from agent.domains.harness.runtime.turn import Turn
from agent.platforms.persistence import memory_index
from agent.platforms.persistence.mongo import personalization_store as store


@pytest.fixture
def memory(monkeypatch):
    coll = Collection()
    monkeypatch.setattr(store, "collection", lambda: coll)
    monkeypatch.setattr(memory_runtime, "context_mode", "retrieve")
    monkeypatch.setattr(memory_runtime, "rag_url", "")
    monkeypatch.setattr(memory_runtime, "rag_api_key", "")
    return coll


@pytest.mark.asyncio
async def test_ordinary_message_recalls_semantic_facts_without_reader(
    memory, monkeypatch
):
    await store.create_memory(
        "u",
        "f",
        MemoryCreate(
            memory_id="coffee", key="drink", text="我喝咖啡只加燕麦奶，不加糖。"
        ),
    )
    reader = AsyncMock(side_effect=AssertionError("快速路径不能额外调用记忆阅读模型"))
    monkeypatch.setattr(inference, "read_context", reader)

    async def retrieve(*args, diagnostics=None):
        diagnostics.update(status="ready", hit_count=1)
        return ["coffee"]

    monkeypatch.setattr(memory_index, "retrieve", retrieve)
    first = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="下午提提神，帮我点一杯吧"
    )
    assert "燕麦奶" in first["personalization"] and "不加糖" in first["personalization"]
    assert first["personalization_diagnostics"]["retrieval"]["status"] == "ready"
    reader.assert_not_called()
    await store.modify_memory("u", "f", "coffee")
    after = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="下午提提神，帮我点一杯吧", previous=first
    )
    assert "燕麦奶" not in after["personalization"]


@pytest.mark.asyncio
async def test_semantic_timeout_keeps_lexical_evidence(memory, monkeypatch):
    await store.create_memory(
        "u",
        "f",
        MemoryCreate(
            memory_id="one", key="拼图", text="在家喜欢拼图，不喜欢高强度运动。"
        ),
    )
    monkeypatch.setattr(memory_runtime, "rag_url", "https://rag.example.test")
    monkeypatch.setattr(memory_runtime, "rag_api_key", "test")
    monkeypatch.setattr(memory_runtime, "retrieve_timeout", 0.02)

    async def slow(request):
        await asyncio.sleep(1)

    monkeypatch.setattr(
        memory_index,
        "client",
        lambda _: httpx.AsyncClient(
            base_url="https://rag.example.test", transport=httpx.MockTransport(slow)
        ),
    )
    started = time.monotonic()
    result = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="在家做什么"
    )
    assert time.monotonic() - started < 0.5
    assert "拼图" in result["personalization"]
    assert result["personalization_diagnostics"]["retrieval"]["status"] == "timeout"


@pytest.mark.asyncio
async def test_fast_context_respects_scope_disabled_and_expiry(memory):
    await store.create_memory(
        "u",
        "farm-a",
        MemoryCreate(
            memory_id="farm", key="工作", text="工作时先检查蓝莓棚", scope="user_farm"
        ),
    )
    assert (
        "蓝莓棚"
        not in (
            await long_term.get_personalization_context(
                user_id="u", farm_uid="farm-b", query="工作"
            )
        )["personalization"]
    )
    assert (
        "蓝莓棚"
        not in (
            await long_term.get_personalization_context(
                user_id="other", farm_uid="farm-a", query="工作"
            )
        )["personalization"]
    )
    assert (
        await long_term.get_personalization_context(
            user_id="u", farm_uid="farm-a", query="工作", temporary=True
        )
        == {}
    )
    doc = await store.load("u")
    await store.update_settings(
        "u", SettingsPatch(expected_revision=doc["revision"], use_saved_memories=False)
    )
    result = await long_term.get_personalization_context(
        user_id="u", farm_uid="farm-a", query="工作"
    )
    assert "蓝莓棚" not in result["personalization"]
    assert result["personalization_diagnostics"]["status"] == "disabled"


def test_semantic_fusion_and_diversity_do_not_rewrite_negative_facts():
    records = [
        {"memory_id": str(i), "text": "休息时喜欢看喜剧片", "key": "休闲"}
        for i in range(20)
    ]
    records += [
        {"memory_id": "other", "text": "休息时不喜欢看恐怖片", "key": "电影"},
        {"memory_id": "music", "text": "空闲喜欢听古典音乐", "key": "音乐"},
    ]
    original = deepcopy(records)
    semantic = ["0", "other", "music"] + [str(i) for i in range(1, 20)]
    result = rank_context_records(records, [str(i) for i in range(20)], semantic)
    assert {"other", "music"} <= {r["memory_id"] for r in result[:5]}
    assert len(result) <= memory_runtime.context_card_limit and records == original


def test_fast_render_budget_never_splits_positive_and_negative(monkeypatch):
    doc = new_document("u")
    selected = [
        {
            "fact": {"memory_id": "one", "text": text},
            "use": "context",
            "applicability": "conditional",
        }
        for text in ["喜欢拿铁", "不加糖" * 100]
    ]
    monkeypatch.setattr(memory_runtime, "context_chars", 850)
    rendered, injected = answer_context(doc, selected, "ready")
    assert not injected and "喜欢拿铁" not in rendered


@pytest.mark.asyncio
async def test_lexical_only_project_survives_semantic_fusion_and_render(
    memory, monkeypatch
):
    await store.create_memory(
        "u",
        "f",
        MemoryCreate(
            memory_id="project",
            key="雾桥纸笺",
            text="雾桥纸笺项目喜欢青绿色，不喜欢米白色",
        ),
    )
    for index in range(20):
        await store.create_memory(
            "u",
            "f",
            MemoryCreate(
                memory_id=f"color-{index}",
                key=f"材料{index}",
                text="挑选手工材料时偏爱低饱和度颜色",
            ),
        )
    monkeypatch.setattr(
        memory_index,
        "retrieve",
        AsyncMock(return_value=[f"color-{index}" for index in range(20)]),
    )
    result = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="雾桥纸笺项目的配色偏好"
    )
    assert "雾桥纸笺" in result["personalization"]
    assert "喜欢青绿色，不喜欢米白色" in result["personalization"]


@pytest.mark.asyncio
async def test_index_write_concurrency_and_idempotent_version(monkeypatch):
    active = peak = 0

    async def handler(request):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return httpx.Response(200, json={"code": "OK"})

    manifest = SimpleNamespace(update_one=AsyncMock())
    record = {"memory_id": "one", "revision": 2, "text": "喜欢读书", "scope": "user"}
    semaphore = asyncio.Semaphore(2)
    async with httpx.AsyncClient(
        base_url="https://rag.example.test", transport=httpx.MockTransport(handler)
    ) as http:
        await asyncio.gather(
            *(
                memory_index._index_record(http, manifest, "owner", record, semaphore)
                for _ in range(6)
            )
        )
    assert peak == 2
    assert {call.args[0]["_id"] for call in manifest.update_one.call_args_list} == {
        f"{memory_runtime.rag_collection}:{memory_index.doc_id('owner', record)}"
    }


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("AGENT_MEMORY_RAG_LIVE") != "1", reason="显式开启独立集合真实语义验收"
)
async def test_live_hybrid_retrieval_with_paraphrase_and_owner_filter(
    monkeypatch, tmp_path
):
    """真实向量/关键词服务；临时集合无论成功失败均精确清理。"""
    collection = "qa_memory_proactive_" + uuid.uuid4().hex
    resource = tmp_path / "rag-collection.txt"
    resource.write_text(collection)
    monkeypatch.setattr(memory_runtime, "rag_collection", collection)
    document = new_document("qa-owner-" + uuid.uuid4().hex)
    record = MemoryCreate(
        memory_id="coffee", key="饮品", text="我喝拿铁只加燕麦奶，不加糖。"
    ).model_dump()
    record.update(
        status="active",
        revision=1,
        source_type="explicit",
        updated_at="2026-10-24T00:00:00+00:00",
    )
    document["memories"] = [record]
    manifest = SimpleNamespace(update_one=AsyncMock())
    async with memory_index.client(30) as http:
        try:
            created = await http.post("/collections", json={"name": collection})
            created.raise_for_status()
            await memory_index._index_record(
                http, manifest, document["_id"], record, asyncio.Semaphore(1)
            )
            stats = {}
            started = time.monotonic()
            hits = await memory_index.retrieve(
                document, "farm", "下午困了，给我推荐一杯提神饮料", diagnostics=stats
            )
            assert hits == ["coffee"] and stats["status"] == "ready", stats
            assert time.monotonic() - started < memory_runtime.retrieve_timeout + 0.5
            foreign = {**document, "_id": "unrelated-user"}
            foreign_stats = {}
            assert (
                await memory_index.retrieve(
                    foreign, "farm", "拿铁", diagnostics=foreign_stats
                )
                == []
            )
            assert foreign_stats["status"] == "ready", foreign_stats
        finally:
            response = await http.delete("/collections/" + collection)
            assert response.status_code in {200, 404}
            resource.unlink()


@pytest.mark.asyncio
async def test_turn_prepares_memory_and_router_concurrently_without_estimate(
    monkeypatch,
):
    from agent.config import settings
    from agent.domains.harness.runtime import engine
    from agent.domains.harness.runtime.turn import Turn

    memory_started, router_started = asyncio.Event(), asyncio.Event()

    async def retrieve(**kwargs):
        memory_started.set()
        await asyncio.wait_for(router_started.wait(), timeout=0.5)
        return {"personalization": "喜欢无糖饮料"}

    async def route(turn):
        router_started.set()
        await asyncio.wait_for(memory_started.wait(), timeout=0.5)

    estimate = AsyncMock(side_effect=AssertionError("快速路径无需步数预估模型"))
    monkeypatch.setattr(settings.context, "estimate_steps", False)
    monkeypatch.setattr(engine.memory, "get_personalization_context", retrieve)
    monkeypatch.setattr(engine, "_route_turn_skills", route)
    monkeypatch.setattr(engine, "_estimate_turn_budget", estimate)
    monkeypatch.setattr(engine, "_setup_turn_runtime", lambda *a, **kw: (None,) * 5)
    turn = Turn(user_id="u", farm_uid="f", user_input="点杯饮料")
    await engine._prepare_turn_runtime(turn)
    assert turn.memory_snapshot["personalization"] == "喜欢无糖饮料"
    estimate.assert_not_called()


@pytest.mark.asyncio
async def test_index_manifest_isolated_when_embedding_collection_changes(monkeypatch):
    manifest = SimpleNamespace(update_one=AsyncMock())
    record = {"memory_id": "one", "revision": 1, "text": "读书", "scope": "user"}
    async with httpx.AsyncClient(
        base_url="https://rag.example.test",
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"code": "OK"})
        ),
    ) as http:
        for name in ["memory_google", "memory_ollama"]:
            monkeypatch.setattr(memory_runtime, "rag_collection", name)
            await memory_index._index_record(
                http, manifest, "owner", record, asyncio.Semaphore(1)
            )
    keys = {call.args[0]["_id"] for call in manifest.update_one.call_args_list}
    assert len(keys) == 2
    assert {key.split(":")[0] for key in keys} == {"memory_google", "memory_ollama"}


@pytest.mark.asyncio
async def test_memory_tool_list_keeps_semantic_hit_outside_lexical_window(
    memory, monkeypatch
):
    for index in range(12):
        await store.create_memory(
            "u",
            "f",
            MemoryCreate(
                memory_id=f"noise-{index}",
                key=f"music-{index}",
                text=f"整理照片时喜欢听第{index}张唱片",
            ),
        )
    await store.create_memory(
        "u",
        "f",
        MemoryCreate(
            memory_id="archive", key="归档", text="相片文件夹先按年份再按月份分类"
        ),
    )
    original = store.load

    async def lexical_window(*args, **kwargs):
        doc = await original(*args, **kwargs)
        if kwargs.get("query") is not None:
            doc["memories"] = [
                r for r in doc["memories"] if r["memory_id"] != "archive"
            ]
        return doc

    monkeypatch.setattr(store, "load", lexical_window)
    retrieve = AsyncMock(return_value=["archive"])
    monkeypatch.setattr(memory_index, "retrieve", retrieve)
    result = await memory_tools.execute(
        Turn(user_id="u", farm_uid="f", user_input="相片如何归档"),
        {"action": "list", "query": "整理照片"},
        "read",
    )
    assert result["ok"] and result["memories"][0]["memory_id"] == "archive"
    assert len(result["memories"]) <= memory_runtime.context_selection_limit
    assert retrieve.call_args.args[1:] == ("f", "整理照片")


@pytest.mark.asyncio
async def test_memory_tool_semantic_lookup_respects_forgetting_owner_and_read_switch(
    memory, monkeypatch
):
    for user, identifier in (("u", "deleted"), ("other", "foreign")):
        await store.create_memory(
            user,
            "f",
            MemoryCreate(memory_id=identifier, key="archive", text="相片按年月归档"),
        )
    await store.modify_memory("u", "f", "deleted")
    retrieve = AsyncMock(return_value=["deleted", "foreign"])
    monkeypatch.setattr(memory_index, "retrieve", retrieve)
    turn = Turn(user_id="u", farm_uid="f", user_input="相片归档")
    result = await memory_tools.execute(turn, {"action": "list"}, "read")
    assert result["ok"] and result["memories"] == []
    control = await store.load("u")
    await store.update_settings(
        "u",
        SettingsPatch(expected_revision=control["revision"], use_saved_memories=False),
    )
    retrieve.reset_mock()
    assert (await memory_tools.execute(turn, {"action": "list"}, "disabled"))[
        "memories"
    ] == []
    retrieve.assert_not_awaited()


@pytest.mark.asyncio
async def test_memory_tool_timeout_does_not_claim_empty_memory(monkeypatch):
    monkeypatch.setattr(
        long_term, "load_context_candidates", AsyncMock(side_effect=TimeoutError)
    )
    result = await memory_tools.execute(
        Turn(user_id="u", farm_uid="f", user_input="相片归档"),
        {"action": "list"},
        "read",
    )
    assert not result["ok"] and result["code"] == "memory_retrieve_timeout"
    assert "memories" not in result


@pytest.mark.asyncio
async def test_short_followup_uses_bounded_user_history_and_invalidates_cache(
    memory, monkeypatch
):
    await store.create_memory(
        "u", "f", MemoryCreate(memory_id="one", key="饮品", text="咖啡喜欢燕麦奶")
    )
    queries = []

    async def retrieve(document, farm_uid, query, *, diagnostics):
        queries.append(query)
        return ["one"]

    monkeypatch.setattr(memory_index, "retrieve", retrieve)
    history = [
        {"role": "user", "content": "咖啡" * 1000},
        {"role": "assistant", "content": "助手臆测的滑雪偏好"},
    ]
    first = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="来一杯", history=history
    )
    assert "咖啡" in queries[0] and "滑雪" not in queries[0]
    assert len(queries[0]) < memory_runtime.retrieval_history_chars + 50
    await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="来一杯", history=history, previous=first
    )
    assert len(queries) == 1
    await long_term.get_personalization_context(
        user_id="u",
        farm_uid="f",
        query="来一杯",
        history=[{"role": "user", "content": "今天改喝茶"}],
        previous=first,
    )
    assert len(queries) == 2 and "改喝茶" in queries[1]


@pytest.mark.skipif(
    os.getenv("AGENT_MEMORY_PROACTIVE_LIVE") != "1",
    reason="显式开启真实主模型的主动注入验收",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,required,forbidden",
    [
        (
            "今天在家放松，给我两个安静的活动建议。",
            ["拼图", "音乐"],
            ["去山间", "建议高强度"],
        ),
        (
            "今天不想拼图，在家休息推荐一个安静的选择。",
            ["音乐"],
            ["推荐你拼图", "可以拼拼图"],
        ),
        ("我通常会选多少片的拼图？仅依据已知信息，不要猜测。", [], ["400片", "1000片"]),
    ],
)
async def test_live_main_model_uses_proactive_context(
    memory, tmp_path, query, required, forbidden
):
    """已知候选的真实模型利用验收，与外部检索命中率和完整 SSE 链路分开统计。"""
    import json
    from pathlib import Path

    from test_memory_context_use import seed

    from agent.domains.harness.memory.personalization import proactive_context
    from agent.platforms.llm.client import MODEL, bounded_completion

    document = await seed()
    plan = proactive_context(document, "f", query)
    context, injected = answer_context(document, plan["selected"], plan["status"])
    started = time.monotonic()
    response = await bounded_completion(
        model=MODEL,
        temperature=0,
        max_tokens=650,
        timeout=30,
        messages=[
            {"role": "system", "content": Path("agent/prompts/system.md").read_text()},
            {"role": "user", "content": context},
            {"role": "user", "content": query},
        ],
    )
    answer = response.choices[0].message.content or ""
    (tmp_path / "proactive-answer.json").write_text(
        json.dumps(
            {
                "query": query,
                "answer": answer,
                "injected_count": len(injected),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            },
            ensure_ascii=False,
        )
    )
    assert answer and all(word in answer for word in required), answer
    assert all(word not in answer for word in forbidden), answer


@pytest.mark.asyncio
async def test_semantic_scope_fusion_does_not_push_farm_to_tail(monkeypatch):
    document = new_document("owner")
    document["memories"] = [
        {
            "memory_id": name,
            "revision": 1,
            "status": "active",
            "scope": scope,
            "farm_uid": "f",
            "text": name,
        }
        for name, scope in [
            ("global-a", "user"),
            ("global-b", "user"),
            ("farm-a", "user_farm"),
        ]
    ]

    def handler(request):
        import json

        scope = json.loads(request.content)["filters"]["scope"]
        return httpx.Response(
            200,
            json={
                "code": "OK",
                "data": {
                    "results": [
                        {"doc_id": memory_index.doc_id("owner", r)}
                        for r in document["memories"]
                        if r["scope"] == scope
                    ],
                    "actual_mode": "hybrid",
                },
            },
        )

    monkeypatch.setattr(memory_runtime, "rag_url", "https://rag.example.test")
    monkeypatch.setattr(memory_runtime, "rag_api_key", "test")
    monkeypatch.setattr(
        memory_index,
        "client",
        lambda _: httpx.AsyncClient(
            base_url="https://rag.example.test", transport=httpx.MockTransport(handler)
        ),
    )
    assert await memory_index.retrieve(document, "f", "工作") == [
        "global-a",
        "farm-a",
        "global-b",
    ]
