"""记忆阅读和回答利用回归：与检索命中率分开验收。"""

import asyncio
import json
import os
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_personalization import Collection

from agent.config import memory_runtime
from agent.domains.harness.context import builder, tokenizer
from agent.domains.harness.memory import inference, long_term
from agent.domains.harness.memory.personalization import (
    MemoryCreate,
    MemoryError,
    SettingsPatch,
    answer_context,
    context_candidates,
    context_text,
)
from agent.platforms.persistence.mongo import personalization_store as store


@pytest.fixture
def memory(monkeypatch):
    monkeypatch.setattr(memory_runtime, "context_mode", "read")
    coll = Collection()
    monkeypatch.setattr(store, "collection", lambda: coll)
    monkeypatch.setattr(
        "agent.platforms.persistence.memory_index.retrieve", AsyncMock(return_value=[])
    )
    return coll


async def seed():
    """同一主题包含正负偏好和不同条件，不能只挑一条正面记录。"""
    rows = [
        ("a", "在家休息时，我喜欢拼风景拼图。", ["在家休息"]),
        ("b", "在家休息时，我不喜欢做高强度运动。", ["在家休息"]),
        ("c", "在家休息时，我喜欢听轻音乐。", ["在家休息"]),
        ("d", "去山间走走时，我喜欢穿舒服的鞋。", ["去山间走走"]),
    ]
    for identity, text, conditions in rows:
        await store.create_memory(
            "u",
            "f",
            MemoryCreate(
                memory_id=identity, key=identity, text=text, conditions=conditions
            ),
        )
    return await store.load("u")


def reading(*choices, searches=()):
    return inference.ContextReading(
        selections=[
            inference.ContextSelection(
                ref=i, use=use, applicability="direct", aspect=str(i)
            )
            for i, use in choices
        ],
        search_queries=list(searches),
    )


@pytest.mark.asyncio
async def test_compiler_references_preserve_original_and_cache_invalidates(
    memory, monkeypatch
):
    await seed()

    async def choose(query, facts, history, **kwargs):
        return reading(
            *[
                (f["ref"], "avoid" if "不喜欢" in f["text"] else "recommend")
                for f in facts
                if "在家" in f["text"]
            ]
        )

    reader = AsyncMock(side_effect=choose)
    monkeypatch.setattr(inference, "read_context", reader)
    query = "在家休息可以做什么"
    first = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query=query
    )
    assert (
        "风景拼图" in first["personalization"]
        and "舒服的鞋" not in first["personalization"]
    )
    assert "避开事项" in first["personalization"]
    second = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query=query, previous=first
    )
    assert second["personalization_diagnostics"]["cached"] and reader.await_count == 1
    await store.modify_memory("u", "f", "a")
    after = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query=query, previous=second
    )
    assert "风景拼图" not in after["personalization"] and reader.await_count == 2
    doc = await store.load("u")
    await store.update_settings(
        "u", SettingsPatch(expected_revision=doc["revision"], use_saved_memories=False)
    )
    disabled = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query=query, previous=after
    )
    assert "轻音乐" not in disabled["personalization"] and reader.await_count == 2
    assert disabled["personalization_diagnostics"]["status"] == "disabled"


@pytest.mark.asyncio
async def test_deletion_during_read_cannot_republish_stale_fact(memory, monkeypatch):
    await seed()

    async def deleting(query, facts, *args, **kwargs):
        index = next(f["ref"] for f in facts if "风景拼图" in f["text"])
        await store.modify_memory("u", "f", "a")
        return reading((index, "recommend"))

    monkeypatch.setattr(inference, "read_context", deleting)
    result = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="在家"
    )
    assert "风景拼图" not in result["personalization"]
    assert result["personalization_diagnostics"]["status"] == "changed_during_read"


@pytest.mark.asyncio
async def test_temporary_and_cache_identity_fences(memory, monkeypatch):
    await seed()
    reader = AsyncMock(return_value=reading())
    monkeypatch.setattr(inference, "read_context", reader)
    first = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="在家"
    )
    assert (
        await long_term.get_personalization_context(
            user_id="u", farm_uid="f", query="在家", temporary=True, previous=first
        )
        == {}
    )
    assert reader.await_count == 1
    other = await long_term.get_personalization_context(
        user_id="other", farm_uid="f", query="在家", previous=first
    )
    assert "拼图" not in other["personalization"]
    await long_term.get_personalization_context(
        user_id="u", farm_uid="other-farm", query="在家", previous=first
    )
    await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="出门", previous=first
    )
    assert reader.await_count == 3


@pytest.mark.asyncio
async def test_timeout_keeps_preferences_without_injecting_raw_candidates(
    memory, monkeypatch
):
    await seed()
    monkeypatch.setattr(memory_runtime, "context_compile_timeout", 0.01)

    async def slow(*args, **kwargs):
        await asyncio.sleep(1)

    monkeypatch.setattr(inference, "read_context", slow)
    result = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="在家"
    )
    assert (
        "田掌柜" in result["personalization"]
        and "风景拼图" not in result["personalization"]
    )
    assert result["personalization_diagnostics"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_selected_expiry_without_revision_change_is_not_cached(
    memory, monkeypatch
):
    doc = await seed()
    reader = AsyncMock(return_value=reading((0, "recommend")))
    monkeypatch.setattr(inference, "read_context", reader)
    first = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="在家"
    )
    selected_id = first["_personalization_cache"]["plan"]["selected"][0]["fact"][
        "memory_id"
    ]
    for record in memory.docs[doc["_id"]]["memories"]:
        if record["memory_id"] == selected_id:
            record["expires_at"] = "2000-01-01T00:00:00+00:00"
    result = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="在家", previous=first
    )
    assert (
        result["personalization_diagnostics"]["injected_count"] == 0
        and reader.await_count == 1
    )


@pytest.mark.asyncio
async def test_bounded_supplementary_reading_and_conflict_cannot_be_truth(
    memory, monkeypatch
):
    await seed()
    reader = AsyncMock(
        side_effect=[
            reading(searches=["在家", "休闲"]),
            reading((0, "recommend"), searches=["禁止第三次"]),
        ]
    )
    monkeypatch.setattr(inference, "read_context", reader)
    load = AsyncMock(wraps=store.load)
    monkeypatch.setattr(store, "load", load)
    result = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="可以做啥"
    )
    assert reader.await_count == 2
    assert reader.call_args.kwargs["can_search"] is False
    assert all(c.kwargs.get("query") != "禁止第三次" for c in load.call_args_list)
    assert result["personalization_diagnostics"]["searches"] == ["在家", "休闲"]


@pytest.mark.asyncio
async def test_model_cannot_reference_unknown_or_duplicate_facts(monkeypatch):
    from agent.platforms.llm import client

    for selections in [
        [{"ref": 7, "use": "answer", "applicability": "direct", "aspect": "偏好"}],
        [{"ref": 0, "use": "answer", "applicability": "direct", "aspect": "偏好"}] * 2,
    ]:
        response = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps({"selections": selections})
                    )
                )
            ]
        )
        monkeypatch.setattr(
            client, "bounded_completion", AsyncMock(return_value=response)
        )
        with pytest.raises(MemoryError, match="引用无效"):
            await inference.read_context(
                "问题", [{"ref": 0, "text": "原文"}], [], can_search=False
            )


@pytest.mark.asyncio
async def test_renderer_budget_fact_integrity_and_placement(memory, monkeypatch):
    doc = await seed()
    doc["active_memory_count"] = 3000
    facts = context_candidates(doc, "f", "在家")
    selected = [
        {
            "fact": f,
            "use": "avoid" if "不喜欢" in f["text"] else "recommend",
            "applicability": "conditional",
        }
        for f in facts
    ]
    text, injected = answer_context(doc, selected, "ready")
    assert text.index("避开事项") < text.index("推荐依据")
    assert "条件成立时才用" in text
    assert (
        len(text) <= memory_runtime.context_chars
        and tokenizer.count_tokens(text) <= memory_runtime.context_tokens
    )
    assert len(injected) > 1
    empty, _ = answer_context(doc, [], "no_relevant_evidence")
    payload = json.loads(
        empty.removeprefix("<user-personalization>\n").removesuffix(
            "\n</user-personalization>"
        )
    )
    assert payload["覆盖范围"]["已发布有效记忆计数"] == 3000
    assert payload["覆盖范围"]["本次提供事实数"] == 0
    monkeypatch.setattr(memory_runtime, "context_tokens", 1000)
    limited, used = answer_context(doc, selected, "ready")
    assert tokenizer.count_tokens(limited) <= 1000
    for entry in used:
        assert entry["fact"]["text"] in limited
        assert entry["fact"]["memory_id"] in limited
    bundle = builder.build_context_bundle(
        "当前问题",
        {
            "personalization": text,
            "messages": [
                {"role": "user", "content": "以前的问题"},
                {"role": "assistant", "content": "以前的回答"},
            ],
        },
    )
    messages = builder.bundle_to_messages(bundle)
    assert messages[-2] == {"role": "user", "content": text}
    assert messages[-1]["content"].startswith("当前问题")


@pytest.mark.asyncio
async def test_candidate_budget_skips_oversized_cards_without_partial_evidence(memory):
    doc = await seed()
    expanded = deepcopy(doc["memories"][0])
    expanded["atoms"] = [
        {"slot": str(i), "text": "很长的记忆" * 100, "state": "active"}
        for i in range(30)
    ]
    doc["memories"].insert(0, expanded)
    facts = context_candidates(doc, "f", "在家")
    assert len(facts) <= memory_runtime.context_fact_limit
    assert (
        sum(len(json.dumps(f, ensure_ascii=False).encode()) for f in facts)
        <= memory_runtime.review_bytes
    )
    assert any("轻音乐" in f["text"] for f in facts)
    assert not any("很长的记忆" in f["text"] for f in facts)


@pytest.mark.asyncio
async def test_candidate_budget_keeps_sibling_exclusions_with_positive_preference(
    memory,
):
    doc = await seed()
    target = deepcopy(doc["memories"][0])
    target["atoms"] = [
        {"slot": "puzzle.count", "text": "拼图选400片", "state": "active"},
        {"slot": "puzzle.avoid", "text": "拼图不买1000片", "state": "active"},
    ]
    distractors = [
        {**deepcopy(doc["memories"][1]), "memory_id": f"other-{i}"} for i in range(80)
    ]
    doc["memories"] = [target, *distractors]
    facts = context_candidates(doc, "f", "拼图选多少片，要避开什么")
    assert len(facts) <= memory_runtime.context_fact_limit
    assert {f["text"] for f in facts if f["memory_id"] == target["memory_id"]} == {
        "拼图选400片",
        "拼图不买1000片",
    }


@pytest.mark.skipif(
    os.getenv("AGENT_MEMORY_READING_LIVE") != "1",
    reason="显式开启真实模型的阅读对照验收",
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query,required,forbidden",
    [
        ("气温挺舒服的我可以在家做啥呢", ("拼图", "音乐"), ("舒服的鞋", "查询工单")),
        ("我在家休息有哪些偏好？", ("拼图", "音乐", "不"), ("喜欢高强度运动",)),
        (
            "今天不要拼图，在家休息推荐一个安静的选择。",
            ("音乐",),
            ("推荐你拼图", "可以拼拼图"),
        ),
        (
            "我今天只想做农场工作，给我一个在家能完成的农场准备建议。",
            ("农",),
            ("推荐拼图", "拼一幅"),
        ),
        pytest.param(
            "我选星海拼图通常选多少片？只根据已保存的记忆回答，不要猜。",
            ("没有",),
            ("400片", "1000片", "主要包含", "只保存"),
            id="unrelated-memory-no-whole-library-claim",
        ),
    ],
)
async def test_live_oracle_reading_comparison(
    memory, tmp_path, query, required, forbidden
):
    """两组使用完全相同的已知正确候选；不以检索率替代最终回答利用。"""
    import time
    from pathlib import Path

    from agent.platforms.llm.client import MODEL, bounded_completion

    doc = await seed()
    facts = context_candidates(doc, "f", query)
    reading_result = await inference.read_context(
        query, [{"ref": i, **f} for i, f in enumerate(facts)], [], can_search=False
    )
    selected = [
        {"fact": facts[s.ref], "use": s.use, "applicability": s.applicability}
        for s in reading_result.selections
    ]
    compiled, injected = answer_context(doc, selected, "ready")
    original = context_text(doc, "f", query, [r["memory_id"] for r in doc["memories"]])
    prompt = Path("agent/prompts/system.md").read_text()
    results = {}
    for variant, context in (("original", original), ("compiled", compiled)):
        started = time.monotonic()
        response = await bounded_completion(
            model=MODEL,
            temperature=0,
            max_tokens=650,
            timeout=30,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
                {"role": "user", "content": query},
            ],
        )
        answer = response.choices[0].message.content or ""
        results[variant] = {
            "answer": answer,
            "passed": all(w in answer for w in required)
            and all(w not in answer for w in forbidden),
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }
    (tmp_path / "reading-comparison.json").write_text(
        json.dumps(
            {"query": query, "results": results, "injected": injected},
            ensure_ascii=False,
            indent=2,
        )
    )
    assert results["compiled"]["passed"], results


@pytest.mark.asyncio
async def test_conflict_remains_uncertain_and_repeated_recommendations_collapse(
    memory, monkeypatch
):
    doc = await seed()
    doc["memories"][0]["atoms"] = [
        {
            "slot": "puzzle",
            "text": "偏好尚有冲突",
            "state": "conflicted",
            "alternatives": [{"text": "喜欢拼图"}, {"text": "不喜欢拼图"}],
        }
    ]
    await store.save(doc, doc["revision"])

    async def select(query, facts, history, **kwargs):
        return inference.ContextReading(
            selections=[
                inference.ContextSelection(
                    ref=f["ref"],
                    use="recommend",
                    applicability="conditional",
                    aspect="活动",
                )
                for f in facts
            ]
        )

    monkeypatch.setattr(inference, "read_context", select)
    result = await long_term.get_personalization_context(
        user_id="u", farm_uid="f", query="在家"
    )
    # 未决冲突必须保留为澄清，不能被推荐去重掩盖或当成可执行偏好。
    assert "待澄清冲突" in result["personalization"]
    assert (
        "喜欢拼图" in result["personalization"]
        and "不喜欢拼图" in result["personalization"]
    )
    assert result["personalization_diagnostics"]["injected_count"] <= 2


@pytest.mark.asyncio
async def test_plain_preference_does_not_claim_save_on_semantic_miss(monkeypatch):
    from agent.domains.harness.memory import tools
    from agent.domains.harness.runtime.turn import Turn

    monkeypatch.setattr(
        tools,
        "assess",
        AsyncMock(return_value=tools.MemoryAssessment(preference_statement=True)),
    )
    turn = Turn(user_id="u", farm_uid="f", user_input="挑选星海拼图时只选300片")
    issue = await tools.completion_guard_issue(turn, "好的，我记住了。以后只选300片。")
    assert issue and issue.can_acknowledge
    issue = await tools.completion_guard_issue(
        turn, "已为你更新拼图偏好", claims_write=True
    )
    assert issue and issue.can_acknowledge
    assert (
        await tools.completion_guard_issue(turn, "了解，你挑选星海拼图时偏好300片。")
        is None
    )
    monkeypatch.setattr(
        tools, "assess", AsyncMock(return_value=tools.MemoryAssessment())
    )
    assert (
        await tools.completion_guard_issue(turn, "根据已保存的记忆，你偏好300片。")
        is None
    )


@pytest.mark.asyncio
async def test_assistant_draft_cannot_authorize_memory_write(monkeypatch):
    from agent.domains.harness.memory import tools
    from agent.domains.harness.runtime.turn import Turn

    assessor = AsyncMock(
        side_effect=[
            tools.MemoryAssessment(requests_persistence=True, claims_persistence=True),
            tools.MemoryAssessment(preference_statement=True),
        ]
    )
    monkeypatch.setattr(tools, "assess", assessor)
    turn = Turn(
        user_id="u",
        farm_uid="f",
        user_input="我现在挑选星海拼图改成500片，仍然不买1000片。",
    )
    issue = await tools.completion_guard_issue(
        turn, "已为你更新拼图偏好", claims_write=True
    )
    assert issue and issue.can_acknowledge
    assert (
        "reply" not in assessor.call_args.kwargs
        and "known_memories" not in assessor.call_args.kwargs
    )


@pytest.mark.asyncio
async def test_memory_tool_lookup_is_query_scoped_and_bounded(memory, monkeypatch):
    from agent.domains.harness.memory import tools
    from agent.domains.harness.runtime.turn import Turn

    await seed()
    await store.create_memory(
        "u",
        "f",
        MemoryCreate(memory_id="puzzle", key="星海拼图", text="星海拼图选400片"),
    )
    original = store.load
    loader = AsyncMock(wraps=original)
    monkeypatch.setattr(store, "load", loader)
    monkeypatch.setattr(memory_runtime, "context_selection_limit", 2)
    turn = Turn(user_id="u", farm_uid="f", user_input="星海拼图")
    result = await tools.execute(turn, {"action": "list"}, "lookup")
    assert loader.call_args.kwargs["query"] == turn.user_input
    assert result["memories"][0]["memory_id"] == "puzzle"
    assert len(result["memories"]) <= 2 and "has_more" not in result
    assert "不会取得下一页" in result["coverage"]
    await tools.execute(turn, {"action": "list", "query": "轻音乐"}, "lookup-other")
    assert loader.call_args.kwargs["query"] == "轻音乐"
