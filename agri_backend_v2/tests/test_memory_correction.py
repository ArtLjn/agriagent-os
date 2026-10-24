"""偏好纠正的完整链路：真实编号、局部更新、后台观察与有界收尾。"""

import os
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from test_agent_step_budget import _ReadSkill, _runtime, _tool
from test_personalization import Collection

from agent.domains.harness.memory import learning, tools
from agent.domains.harness.memory.facts import AtomicFact, initialize_atoms
from agent.domains.harness.memory.personalization import (
    MemoryCreate,
    MemoryPatch,
    context_text,
)
from agent.domains.harness.runtime import engine
from agent.domains.harness.runtime.turn import StopReason, Turn
from agent.platforms.persistence.mongo import personalization_store as store

pytestmark = pytest.mark.usefixtures("memory_writer_stub")

_assess, _grounded = tools.assess, tools.content_is_grounded
_llm_stream = engine._call_llm_stream
ORIGINAL = "喜欢西瓜、芒果、葡萄和草莓"
CORRECTED = "喜欢西瓜、芒果和草莓，不喜欢葡萄"


@pytest.fixture
def collection(monkeypatch):
    coll = Collection()
    monkeypatch.setattr(store, "collection", lambda: coll)
    return coll


@pytest_asyncio.fixture
async def memory(collection):
    return await store.create_memory(
        "u",
        "f",
        MemoryCreate(
            memory_id="fruit-real-id",
            key="fruit",
            text=ORIGINAL,
            category="preference",
        ),
    )


@pytest.mark.asyncio
async def test_projection_has_real_id_and_revision(memory):
    doc = await store.load("u")
    projected = context_text(doc, "f")
    assert '"memory_id": "fruit-real-id"' in projected
    assert '"revision": 1' in projected


@pytest.mark.asyncio
async def test_update_checks_authoritative_old_facts_and_preserves_unmentioned_details(
    memory, monkeypatch, memory_assessment_stub
):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        authorized=True, requests_persistence=True
    )
    grounding = AsyncMock(return_value=True)
    monkeypatch.setattr(tools, "content_is_grounded", grounding)
    turn = Turn(user_id="u", farm_uid="f", user_input="我不喜欢吃葡萄了")
    result = await tools.execute(
        turn,
        {
            "action": "update",
            "memory_id": memory["memory_id"],
            "text": CORRECTED,
            "evidence": turn.user_input,
        },
        "correct",
    )
    assert result["persisted"] is True
    known = memory_assessment_stub.call_args.kwargs["known_memories"]
    assert known == [
        {k: memory[k] for k in ("memory_id", "text", "conditions", "revision")}
    ]
    assert grounding.call_args.kwargs["known_memories"] == known
    records = (await store.load("u"))["memories"]
    assert len(records) == 1 and records[0]["text"] == CORRECTED


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "memory_id,user_id,farm_uid", [("3", "u", "f"), ("fruit-real-id", "other", "f")]
)
async def test_fabricated_or_other_owner_ids_require_lookup_without_model_review(
    memory, memory_assessment_stub, memory_id, user_id, farm_uid
):
    turn = Turn(user_id=user_id, farm_uid=farm_uid, user_input="我不喜欢吃葡萄了")
    result = await tools.execute(
        turn,
        {
            "action": "update",
            "memory_id": memory_id,
            "text": CORRECTED,
            "evidence": turn.user_input,
        },
        "bad-id",
    )
    assert result["code"] == "memory_not_found" and result["retryable"] is True
    memory_assessment_stub.assert_not_called()
    assert (await store.load("u"))["memories"][0]["text"] == ORIGINAL


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["update", "forget"])
async def test_concurrent_edit_invalidates_reviewed_mutation(
    memory, monkeypatch, action
):
    async def edit_during_review(*args, **kwargs):
        await store.modify_memory(
            "u",
            "f",
            memory["memory_id"],
            MemoryPatch(expected_revision=1, text="我现在只喜欢苹果"),
        )
        return True

    monkeypatch.setattr(tools, "content_is_grounded", edit_during_review)
    turn = Turn(user_id="u", farm_uid="f", user_input="我不喜欢吃葡萄了")
    result = await tools.execute(
        turn,
        {
            "action": action,
            "memory_id": memory["memory_id"],
            "text": CORRECTED,
            "evidence": turn.user_input,
        },
        "race",
    )
    assert result["code"] == "memory_version_conflict" and result["retryable"] is True
    assert (await store.load("u"))["memories"][0]["text"] == "我现在只喜欢苹果"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "relation,old_task,updated",
    [
        ("contradict", False, True),
        ("contradict", True, False),
        ("merge", False, False),
        ("reinforce", False, False),
    ],
)
async def test_new_correction_can_update_explicit_fact_but_other_observation_cannot(
    memory, relation, old_task, updated
):
    doc = await store.load("u")
    timestamp = time.time() - 60 if old_task else time.time() + 1
    task = {
        "user_id": "u",
        "farm_uid": "f",
        "turn_id": "correct",
        "conversation_id": "new-session",
        "generation": doc["memory_generation"],
        "learning_generation": doc["learning_generation"],
        "expected_revision": doc["revision"],
        "observed_at": timestamp,
        "text": "我不喜欢吃葡萄了",
        "normalized_atoms": {
            memory["memory_id"]: initialize_atoms(
                memory,
                [
                    AtomicFact(slot=fruit, text="喜欢" + fruit, evidence=fruit)
                    for fruit in ("西瓜", "芒果", "葡萄", "草莓")
                ],
            )
        },
    }
    candidate = learning.Candidate(
        key="fruit",
        text="不喜欢葡萄",
        evidence=task["text"],
        category="preference",
        relation=relation,
        target_memory_id=memory["memory_id"],
        slot="葡萄",
        target_slot="葡萄",
        scope="user",
    )
    await learning.apply_candidates(task, [candidate])
    records = (await store.load("u"))["memories"]
    assert len(records) == 1
    if updated:
        assert records[0]["text"] == "喜欢西瓜；喜欢芒果；不喜欢葡萄；喜欢草莓"
    else:
        assert records[0]["text"] == ORIGINAL
    assert records[0]["source_type"] == ("inferred" if updated else "explicit")


@pytest.mark.asyncio
async def test_observation_only_closes_turn_before_another_model_write(
    monkeypatch, memory_assessment_stub
):
    memory_assessment_stub.side_effect = AssertionError("观察结论不能被再次审查推翻")
    execute = AsyncMock(return_value=dict(tools.OBSERVATION_ONLY_RESULT))
    monkeypatch.setattr(tools, "execute", execute)
    _, calls, _, approve = _runtime(
        monkeypatch, [_tool(tools.TOOL_NAME, "observation")]
    )
    turn = Turn(user_input="我不喜欢吃葡萄了", max_steps=8)
    events = [event async for event in engine.run_turn(turn, approve)]
    assert execute.await_count == len(calls) == 1
    assert turn.status == "completed" and turn.stop_reason == StopReason.MODEL_COMPLETED
    assert turn.final_answer == tools.PREFERENCE_ACKNOWLEDGEMENT
    assert sum(e["type"] == "done" for e in events) == 1
    assert not any(e["type"] == "doom_loop_warning" for e in events)
    memory_assessment_stub.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("retryable,expected_calls", [(False, 1), (True, 2)])
async def test_failed_memory_calls_have_bounded_repair_instead_of_doom_loop(
    monkeypatch, retryable, expected_calls
):
    execute = AsyncMock(
        return_value={
            "ok": False,
            "persisted": False,
            "retryable": retryable,
            "code": "memory_not_found"
            if retryable
            else "memory_explicit_intent_required",
            "message": "未能修改记忆",
        }
    )
    monkeypatch.setattr(tools, "execute", execute)
    _, calls, _, approve = _runtime(
        monkeypatch, [_tool(tools.TOOL_NAME, str(i)) for i in range(expected_calls)]
    )
    turn = Turn(user_input="修改记忆", max_steps=8)
    events = [event async for event in engine.run_turn(turn, approve)]
    assert execute.await_count == len(calls) == expected_calls
    assert turn.stop_reason == StopReason.TOOL_FAILED
    assert not any(e["type"] == "doom_loop_warning" for e in events)


@pytest.mark.asyncio
async def test_invalid_id_can_be_repaired_by_lookup_then_update(memory, monkeypatch):
    monkeypatch.setattr(tools, "content_is_grounded", AsyncMock(return_value=True))
    monkeypatch.setattr(
        engine.memory, "get_personalization_context", AsyncMock(return_value={})
    )
    responses = []
    for index, arguments in enumerate(
        [
            {"action": "update", "memory_id": "3", "text": CORRECTED},
            {"action": "list"},
            {"action": "update", "memory_id": memory["memory_id"], "text": CORRECTED},
        ]
    ):
        result = _tool(tools.TOOL_NAME, str(index))
        result.tool_calls[0]["arguments"] = {
            **arguments,
            "evidence": "我不喜欢吃葡萄了",
        }
        responses.append(result)
    responses.append(
        engine._LlmResult(full_content="已更新你的水果偏好，保留其他水果。")
    )
    _, calls, _, approve = _runtime(monkeypatch, responses)
    turn = Turn(user_id="u", farm_uid="f", user_input="我不喜欢吃葡萄了", max_steps=5)
    _ = [e async for e in engine.run_turn(turn, approve)]
    assert turn.status == "completed" and len(calls) == 4
    assert (await store.load("u"))["memories"][0]["text"] == CORRECTED


@pytest.mark.asyncio
async def test_same_batch_observations_do_not_execute_twice(monkeypatch):
    execute = AsyncMock(return_value=dict(tools.OBSERVATION_ONLY_RESULT))
    monkeypatch.setattr(tools, "execute", execute)
    result = _tool(tools.TOOL_NAME, "first")
    result.tool_calls.extend(_tool(tools.TOOL_NAME, "repeated").tool_calls)
    _, calls, _, approve = _runtime(monkeypatch, [result])
    turn = Turn(user_input="我喜欢吃水果", max_steps=8)
    events = [e async for e in engine.run_turn(turn, approve)]
    assert execute.await_count == len(calls) == 1
    assert turn.status == "completed"
    assert sum(e["type"] == "tool_finished" for e in events) == 2


@pytest.mark.asyncio
async def test_mixed_request_continues_business_and_does_not_reopen_memory(monkeypatch):
    execute = AsyncMock(return_value=dict(tools.OBSERVATION_ONLY_RESULT))
    monkeypatch.setattr(tools, "execute", execute)
    read = _ReadSkill()
    first = engine._LlmResult(
        tool_calls=[
            {
                "id": "memory",
                "name": tools.TOOL_NAME,
                "arguments": {"action": "remember"},
            },
            {"id": "read", "name": read.name, "arguments": {}},
        ]
    )
    _, calls, _, approve = _runtime(
        monkeypatch,
        [first, engine._LlmResult(full_content="查询到芒果茬口，也了解你的偏好。")],
        skills=[read],
    )
    turn = Turn(user_input="我不喜欢吃葡萄了，查一下茬口", max_steps=8)
    _ = [e async for e in engine.run_turn(turn, approve)]
    assert execute.await_count == read.calls == 1 and len(calls) == 2
    assert turn.status == "completed"
    assert all(
        t.get("function", {}).get("name") != tools.TOOL_NAME for t in calls[-1]["tools"]
    )


@pytest.mark.skipif(
    os.getenv("AGENT_ROUTING_LIVE") != "1", reason="仅显式开启真实模型回放"
)
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,text,user_input,allowed",
    [
        ("update", CORRECTED, "我不喜欢吃葡萄了", False),
        ("update", "喜欢西瓜、芒果和草莓", "我不喜欢吃葡萄了", False),
        ("update", "喜欢香蕉和草莓", "我不喜欢吃葡萄了", False),
        ("forget", None, "我不喜欢吃葡萄了", False),
        ("forget", None, "忘掉整条水果偏好记忆", True),
    ],
)
async def test_live_partial_correction_preserves_other_fruits_without_reapproval(
    memory, monkeypatch, action, text, user_input, allowed
):
    monkeypatch.setattr(tools, "assess", _assess)
    monkeypatch.setattr(tools, "content_is_grounded", _grounded)
    turn = Turn(user_id="u", farm_uid="f", user_input=user_input)
    result = await tools.execute(
        turn,
        {
            "action": action,
            "memory_id": memory["memory_id"],
            "text": text,
            "evidence": turn.user_input,
        },
        "live-correct",
    )
    assert result.get("persisted") is allowed, result
    record = (await store.load("u"))["memories"][0]
    assert record["text"] == ((text or "") if allowed else ORIGINAL)
    assert record["status"] == (
        "deleted" if allowed and action == "forget" else "active"
    )


@pytest.mark.skipif(
    os.getenv("AGENT_ROUTING_LIVE") != "1", reason="仅显式开启真实模型回放"
)
@pytest.mark.asyncio
async def test_live_correction_from_model_routing_through_learning(memory, monkeypatch):
    """主模型自行选路，再执行实际语义审查和学习；全部持久化隔离到内存替身。"""
    from agent.domains.harness.tools.registry import SkillRegistry

    _, _, approvals, approve = _runtime(monkeypatch, [])
    monkeypatch.setattr(tools, "assess", _assess)
    monkeypatch.setattr(tools, "content_is_grounded", _grounded)
    monkeypatch.setattr(engine, "_call_llm_stream", _llm_stream)

    async def prepare(turn):
        prompt = Path("agent/prompts/system.md").read_text()
        turn.messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": turn.user_input},
        ]
        registry = SkillRegistry.from_skills([])
        return engine._TurnRuntime(
            registry,
            [tools.TOOL_SCHEMA],
            registry,
            engine.verify.CallTracker(),
            {"plan": None},
        )

    async def projection(**kwargs):
        doc = await store.load("u")
        return {
            "personalization": context_text(doc, "f"),
            "personalization_revision": doc["revision"],
        }

    monkeypatch.setattr(engine, "_prepare_turn_runtime", prepare)
    monkeypatch.setattr(engine.memory, "get_personalization_context", projection)
    turn = Turn(user_id="u", farm_uid="f", user_input="我不喜欢吃葡萄了", max_steps=4)
    events = [event async for event in engine.run_turn(turn, approve)]
    assert turn.status == "completed", (turn.stop_reason, turn.final_answer)
    assert not approvals and not any(e["type"] == "doom_loop_warning" for e in events)

    # 正常收尾后的 Worker 使用同一套真实抽取和归并，无需用户再确认。
    doc = await store.load("u")
    candidates = await learning.extract(turn.user_input, doc["memories"])
    await learning.apply_candidates(
        {
            "user_id": "u",
            "farm_uid": "f",
            "turn_id": turn.turn_id,
            "conversation_id": "live-correction",
            "text": turn.user_input,
            "observed_at": turn.accepted_at,
            "expected_revision": doc["revision"],
            "generation": doc["memory_generation"],
            "learning_generation": doc["learning_generation"],
            "normalized_atoms": {
                m["memory_id"]: m["atoms"] for m in doc["memories"] if "atoms" in m
            },
        },
        candidates,
    )
    records = (await store.load("u"))["memories"]
    assert len(records) == 1 and records[0]["status"] == "active", records
    assert all(fruit in records[0]["text"] for fruit in ("西瓜", "芒果", "草莓"))
    assert records[0]["text"] != ORIGINAL, records
    assert await _grounded(
        tools.MemoryCommand(
            action="update", text=records[0]["text"], memory_id=memory["memory_id"]
        ),
        [turn.user_input],
        known_memories=[memory],
    ), records
