"""长时记忆工具、学习屏障、语义隔离与临时模式回归。"""

import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from test_personalization import Collection

from agent.domains.harness.memory import inference, learning, tools
from agent.domains.harness.memory.long_term import get_personalization_context
from agent.domains.harness.memory.personalization import (
    MemoryCreate,
    MemoryError,
    SettingsPatch,
)
from agent.platforms.persistence import memory_index
from agent.platforms.persistence.mongo import personalization_store as store

pytestmark = pytest.mark.usefixtures("memory_writer_stub")

_real_assess = tools.assess


@pytest.mark.asyncio
@pytest.mark.parametrize("fenced", [False, True])
async def test_memory_assessment_accepts_strict_json_with_optional_fence(
    monkeypatch, fenced
):
    from agent.platforms.llm import client

    raw = '{"authorized":false,"preference_statement":true}'
    if fenced:
        raw = f"```json\n{raw}\n```"
    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=raw))]
            )
        ),
    )
    result = await _real_assess("我喜欢吃西瓜")
    assert result.preference_statement and not result.authorized


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "raw",
    [
        '说明：{"authorized":true}',
        '```json\n{"authorized":"true"}\n```',
        '```json\n{"authorized":true}\n```后续文字',
    ],
)
async def test_memory_assessment_rejects_mixed_text_and_untyped_authorization(
    monkeypatch, raw
):
    from pydantic import ValidationError

    from agent.platforms.llm import client

    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=raw))]
            )
        ),
    )
    with pytest.raises(ValidationError):
        await _real_assess("我喜欢吃西瓜")


@pytest.fixture
def collection(monkeypatch):
    coll = Collection()
    monkeypatch.setattr(store, "collection", lambda: coll)
    return coll


@pytest.mark.asyncio
async def test_tool_updates_settings_and_temporary_denies_storage(collection):
    turn = SimpleNamespace(
        user_id="u",
        farm_uid="f",
        temporary=False,
        turn_id="t",
        user_input="记住，以后回答简洁一些",
    )
    result = await tools.execute(
        turn,
        {
            "action": "configure",
            "preferences": {"detail_level": "concise"},
            "evidence": "以后回答简洁一些",
        },
        "call",
    )
    assert result["persisted"]
    assert (await store.load("u"))["settings"]["detail_level"] == "concise"
    failed = await tools.execute(
        turn, {"action": "remember", "text": "测试", "evidence": "伪造的原文"}, "call"
    )
    assert failed["code"] == "memory_evidence_required"
    turn.temporary = True
    assert (await tools.execute(turn, {"action": "list"}, "call"))[
        "code"
    ] == "memory_disabled_for_temporary_session"
    assert (
        await get_personalization_context(user_id="u", farm_uid="f", temporary=True)
        == {}
    )


async def enable_learning():
    return await store.update_settings(
        "u", SettingsPatch(expected_revision=0, auto_learn_enabled=True)
    )


def task(doc, turn="1", conversation="a"):
    return {
        "user_id": "u",
        "farm_uid": "f",
        "turn_id": turn,
        "conversation_id": conversation,
        "generation": doc["memory_generation"],
        "learning_generation": doc["learning_generation"],
    }


@pytest.mark.asyncio
async def test_learning_requires_independent_evidence_and_never_recreates_deleted(
    collection,
):
    doc = await enable_learning()
    candidate = learning.Candidate(
        key="response.detail_level",
        text="喜欢简洁回答",
        evidence="简洁",
    )
    first = task(doc)
    await learning.apply_candidates(first, [candidate])
    await learning.apply_candidates(first, [candidate])
    record = (await store.load("u"))["memories"][0]
    assert record["evidence_count"] == 1 and record["status"] == "active"
    await learning.apply_candidates(task(doc, "2", "b"), [candidate])
    await learning.apply_candidates(task(doc, "3", "b"), [candidate])
    record = (await store.load("u"))["memories"][0]
    assert record["status"] == "active"
    await store.modify_memory("u", "f", record["memory_id"])
    await learning.apply_candidates(task(doc, "4", "c"), [candidate])
    assert (await store.load("u"))["memories"][0]["status"] == "deleted"


@pytest.mark.asyncio
async def test_closed_learning_and_clear_invalidate_pending_tasks(collection):
    doc = await enable_learning()
    candidate = learning.Candidate(key="cost", text="成本先看异常", evidence="先看异常")
    pending = task(doc)
    await store.update_settings(
        "u", SettingsPatch(expected_revision=doc["revision"], auto_learn_enabled=False)
    )
    await learning.apply_candidates(pending, [candidate])
    assert not (await store.load("u"))["memories"]
    current = await store.load("u")
    await store.update_settings(
        "u",
        SettingsPatch(expected_revision=current["revision"], auto_learn_enabled=True),
    )
    await learning.apply_candidates(pending, [candidate])
    assert not (await store.load("u"))["memories"]
    current = await store.load("u")
    pending = task(current)
    await store.clear_memories("u", "f")
    await learning.apply_candidates(pending, [candidate])
    assert not (await store.load("u"))["memories"]


@pytest.mark.asyncio
async def test_explicit_setting_blocks_inferred_counterpart(collection):
    doc = await enable_learning()
    await store.update_settings(
        "u", SettingsPatch(expected_revision=doc["revision"], detail_level="detailed")
    )
    await learning.apply_candidates(
        task(doc),
        [
            learning.Candidate(
                key="response.detail_level",
                text="简洁",
                evidence="简洁",
            )
        ],
    )
    assert not (await store.load("u"))["memories"]


@pytest.mark.asyncio
async def test_semantic_filters_and_authoritative_version(collection, monkeypatch):
    record = await store.create_memory(
        "u", "f", MemoryCreate(memory_id="m", key="cost", text="成本先看异常")
    )
    document = await store.load("u")
    calls = []

    def handler(request):
        body = json.loads(request.content)
        calls.append(body)
        return httpx.Response(
            200,
            json={
                "code": "OK",
                "data": {
                    "results": [
                        {"doc_id": "another-user"},
                        {"doc_id": memory_index.doc_id(document["_id"], record)},
                    ]
                },
            },
        )

    monkeypatch.setattr(memory_index.cfg, "rag_url", "https://rag.example.test")
    monkeypatch.setattr(memory_index.cfg, "rag_api_key", "test-only")
    monkeypatch.setattr(
        memory_index,
        "client",
        lambda _: httpx.AsyncClient(
            base_url="https://rag.example.test", transport=httpx.MockTransport(handler)
        ),
    )
    assert await memory_index.retrieve(document, "f", "成本") == ["m"]
    assert all(call["filters"]["owner"] == document["_id"] for call in calls)
    assert calls[1]["filters"]["farm_uid"] == "f"
    await store.modify_memory("u", "f", "m")
    assert await memory_index.retrieve(await store.load("u"), "f", "成本") == []


@pytest.mark.asyncio
async def test_rag_failure_falls_back_without_breaking_preferences(
    collection, monkeypatch
):
    monkeypatch.setattr(memory_index.cfg, "rag_url", "https://rag.example.test")
    monkeypatch.setattr(memory_index.cfg, "rag_api_key", "test-only")
    monkeypatch.setattr(
        memory_index,
        "client",
        lambda _: httpx.AsyncClient(
            base_url="https://rag.example.test",
            transport=httpx.MockTransport(lambda _: httpx.Response(503)),
        ),
    )
    result = await get_personalization_context(user_id="u", farm_uid="f", query="成本")
    assert "田掌柜" in result["personalization"]


@pytest.mark.asyncio
async def test_queue_recovery_drops_disabled_source_without_llm(
    collection, monkeypatch
):
    doc = await enable_learning()
    current = await store.update_settings(
        "u", SettingsPatch(expected_revision=doc["revision"], auto_learn_enabled=False)
    )
    queued = {**task(doc), "_id": "job", "attempts": 1, "text": "原文"}
    queue = SimpleNamespace(
        update_many=AsyncMock(),
        find_one_and_update=AsyncMock(return_value=queued),
        update_one=AsyncMock(),
    )
    monkeypatch.setattr(learning, "jobs", lambda: queue)
    extractor = AsyncMock()
    monkeypatch.setattr(learning, "extract", extractor)
    assert await learning.process_one()
    extractor.assert_not_called()
    assert "text" in queue.update_one.call_args.args[1]["$unset"]
    assert (await store.load("u"))["revision"] == current["revision"]


@pytest.mark.asyncio
async def test_confirmation_removes_expiry_and_secret_never_persists(collection):
    from agent.domains.harness.memory.personalization import MemoryError, MemoryPatch

    doc = await enable_learning()
    await learning.apply_candidates(
        task(doc),
        [learning.Candidate(key="cost", text="先看成本", evidence="先看成本")],
    )
    candidate = (await store.load("u"))["memories"][0]
    confirmed = await store.modify_memory(
        "u",
        "f",
        candidate["memory_id"],
        MemoryPatch(expected_revision=1, status="active"),
    )
    assert confirmed["source_type"] == "explicit" and confirmed["expires_at"] is None
    with pytest.raises(MemoryError) as error:
        await store.create_memory(
            "u",
            "f",
            MemoryCreate(
                memory_id="secret", key="secret", text="api_key: example-credential"
            ),
        )
    assert error.value.code == "memory_sensitive_content"
    assert "example-credential" not in str(await store.load("u"))


def test_old_tool_snapshots_are_removed_after_control_change():
    messages = [
        {
            "role": "tool",
            "name": tools.TOOL_NAME,
            "content": json.dumps(
                {"ok": True, "memory_revision": 1, "result": "已删除内容"}
            ),
        }
    ]
    tools.discard_stale_results(messages, 2)
    assert "已删除内容" not in messages[0]["content"]


@pytest.mark.parametrize("revision", [None, 1, 2])
def test_failed_memory_results_keep_original_rejection(revision):
    result = {
        "ok": False,
        "persisted": False,
        "code": "memory_explicit_intent_required",
        "message": "普通偏好由自动学习处理",
    }
    messages = [
        {"role": "tool", "name": tools.TOOL_NAME, "content": json.dumps(result)}
    ]
    tools.discard_stale_results(messages, revision)
    assert json.loads(messages[0]["content"]) == result


@pytest.mark.asyncio
@pytest.mark.parametrize("claim", ["claims_persistence", "claims_memory_failure"])
@pytest.mark.parametrize("attempted", [False, True])
async def test_ordinary_preference_acknowledges_without_forcing_memory_write(
    memory_assessment_stub, claim, attempted
):
    from agent.domains.harness.runtime import engine, verify
    from agent.domains.harness.runtime.turn import Turn

    memory_assessment_stub.return_value = tools.MemoryAssessment(
        preference_statement=True, **{claim: True}
    )
    turn = Turn(user_input="我还喜欢草莓葡萄", step_count=1)
    tracker = verify.CallTracker()
    if attempted:
        tracker.record(tools.TOOL_NAME, {}, risk_level="write_confirm")
        tracker.calls[-1]["persisted"] = False
    events = [
        event
        async for event in engine._emit_final_answer(
            turn, "记忆系统又出错了，稍后再告诉我一次", None, tracker
        )
    ]
    assert turn.status == "completed"
    assert turn.final_answer == tools.PREFERENCE_ACKNOWLEDGEMENT
    assert turn.write_guard_attempts == 0
    assert not turn.messages
    assert not any(event["type"] in {"error", "tool_started"} for event in events)
    assert sum(event["type"] == "final_answer" for event in events) == 1


@pytest.mark.asyncio
async def test_ordinary_preference_tool_misroute_never_accesses_persistence(
    monkeypatch, memory_assessment_stub
):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        preference_statement=True
    )
    load = AsyncMock(side_effect=AssertionError("普通偏好不能触发显式记忆存储"))
    monkeypatch.setattr(store, "load", load)
    turn = SimpleNamespace(
        user_input="我喜欢吃西瓜", temporary=False, turn_id="ordinary"
    )
    result = await tools.execute(
        turn,
        {"action": "remember", "text": "喜欢西瓜", "evidence": "我喜欢吃西瓜"},
        "call",
    )
    assert result["ok"] and not result["persisted"]
    assert result["code"] == "memory_observation_only"
    load.assert_not_awaited()


@pytest.mark.asyncio
async def test_unrequested_memory_claim_does_not_instruct_tool_execution(
    memory_assessment_stub,
):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        claims_persistence=True
    )
    turn = SimpleNamespace(
        user_input="我喜欢西瓜", messages=[], temporary=False, turn_id="guard"
    )
    issue = await tools.completion_guard_issue(turn, "已经长期保存了")
    assert issue and "撤回保存声明" in issue.message
    assert "请先调用" not in issue.message


@pytest.mark.asyncio
async def test_explicit_memory_request_is_not_downgraded_to_acknowledgement(
    memory_assessment_stub,
):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        preference_statement=True, requests_persistence=True, claims_persistence=True
    )
    turn = SimpleNamespace(
        user_input="请长期记住我喜欢西瓜", messages=[], temporary=False, turn_id="guard"
    )
    issue = await tools.completion_guard_issue(turn, "保存好了")
    assert issue and not issue.can_acknowledge
    assert "执行已授权" in issue.message


@pytest.mark.asyncio
async def test_historical_memory_failure_is_not_current_tool_evidence(
    memory_assessment_stub,
):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        claims_memory_failure=True
    )
    turn = SimpleNamespace(
        user_input="查一下天气", messages=[], temporary=False, turn_id="guard"
    )
    issue = await tools.completion_guard_issue(turn, "本轮记忆保存失败了")
    assert issue and not issue.can_acknowledge
    assert "本轮没有调用" in issue.message


@pytest.mark.asyncio
async def test_preference_acknowledgement_cannot_hide_other_business_calls(
    memory_assessment_stub,
):
    from agent.domains.harness.runtime import engine, verify
    from agent.domains.harness.runtime.turn import Turn

    memory_assessment_stub.return_value = tools.MemoryAssessment(
        preference_statement=True, claims_persistence=True
    )
    tracker = verify.CallTracker()
    tracker.record("get_weather", {}, risk_level="read")
    turn = Turn(user_input="我喜欢晴天，查一下明天的天气", step_count=1, max_steps=1)
    _ = [
        event
        async for event in engine._emit_final_answer(turn, "记住了", None, tracker)
    ]
    assert turn.status == "failed"
    assert turn.final_answer != tools.PREFERENCE_ACKNOWLEDGEMENT


@pytest.mark.asyncio
async def test_enqueue_rejects_turn_started_before_toggle_or_clear(
    collection, monkeypatch
):
    await enable_learning()
    turn = SimpleNamespace(
        temporary=False,
        status="completed",
        user_id="u",
        accepted_at=time.time(),
    )
    queue = SimpleNamespace(update_one=AsyncMock())
    monkeypatch.setattr(learning, "jobs", lambda: queue)
    await store.clear_memories("u", "f")
    await learning.enqueue(turn)
    queue.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_rest_crud_isolation_conflict_and_clear(collection, monkeypatch):
    from fastapi import FastAPI

    from agent.api import api_router
    from agent.api import personalization as api

    app = FastAPI()
    app.include_router(api_router)
    monkeypatch.setattr(
        api, "parse_identity", lambda token: {"user_id": token or "u", "farm_uid": "f"}
    )
    monkeypatch.setattr(
        api, "require_identity_permission", lambda principal, _: principal
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test/api/v2"
    ) as client:
        assert (await client.get("/me/personalization")).json()["revision"] == 0
        assert (
            await client.patch(
                "/me/personalization", json={"expected_revision": 0, "nickname": "农友"}
            )
        ).status_code == 200
        assert (
            await client.patch(
                "/me/personalization", json={"expected_revision": 0, "nickname": "旧值"}
            )
        ).status_code == 409
        response = await client.post(
            "/me/memories",
            json={
                "memory_id": "one",
                "key": "cost",
                "text": "先看异常",
                "scope": "user_farm",
            },
        )
        assert response.status_code == 200
        assert (
            await client.get("/me/memories", headers={"Authorization": "other"})
        ).json()["total"] == 0
        assert (
            await client.delete("/me/memories/one", headers={"Authorization": "other"})
        ).status_code == 404
        assert (
            await client.patch(
                "/me/memories/one", json={"expected_revision": 1, "text": "先看成本"}
            )
        ).status_code == 200
        assert (await client.post("/me/memories/clear")).json()["cleared"] == 1
        assert (await client.get("/me/memories")).json()["total"] == 0
        assert (await client.get("/me/personalization")).json()["nickname"] == "农友"


@pytest.mark.asyncio
async def test_index_initializes_collection_and_cleans_deleted_revision(
    collection, monkeypatch
):
    record = await store.create_memory(
        "u", "f", MemoryCreate(memory_id="one", key="cost", text="先看成本")
    )
    document = await store.load("u")
    identifier = memory_index.doc_id(document["_id"], record)
    entries = [{"_id": identifier, "owner": document["_id"], "status": "ready"}]

    class Cursor:
        def sort(self, *_):
            return self

        def limit(self, *_):
            return self

        async def __aiter__(self):
            for entry in entries:
                yield entry

    manifest = SimpleNamespace(
        find_one=AsyncMock(return_value=None),
        update_one=AsyncMock(),
        find=lambda _: Cursor(),
    )
    collection.database = {memory_index.MANIFEST_COLLECTION: manifest}
    collection.find_one_and_update = AsyncMock(return_value=document)
    collection.update_one = AsyncMock()
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"code": "OK", "data": {}})

    monkeypatch.setattr(memory_index.cfg, "rag_url", "https://rag.example.test")
    monkeypatch.setattr(memory_index.cfg, "rag_api_key", "test-only")
    monkeypatch.setattr(
        memory_index,
        "client",
        lambda _: httpx.AsyncClient(
            base_url="https://rag.example.test", transport=httpx.MockTransport(handler)
        ),
    )
    await memory_index.sync_one()
    assert [r.url.path for r in requests] == ["/collections", "/ingest"]
    from urllib.parse import parse_qs

    payload = parse_qs(requests[1].content.decode())
    metadata = json.loads(payload["metadata_json"][0])
    assert metadata["owner"] == store.owner_key("u") and metadata["scope"] == "user"
    assert collection.update_one.call_args.args[1]["$set"]["index_pending"] is False
    await store.modify_memory("u", "f", "one")
    collection.find_one_and_update.return_value = None
    await memory_index.sync_one()
    assert requests[-1].method == "DELETE" and requests[-1].url.path.endswith(
        identifier
    )
    assert manifest.update_one.call_args.args[1]["$set"]["status"] == "removed"


@pytest.mark.asyncio
async def test_runtime_dispatch_records_real_memory_write(collection):
    from agent.domains.harness.runtime import engine, verify
    from agent.domains.harness.runtime.turn import Turn

    turn = Turn(user_id="u", farm_uid="f", user_input="记住以后先给结论")
    tracker = verify.CallTracker()
    events = [
        event
        async for event in engine._dispatch_tool_calls(
            tool_calls=[
                {
                    "id": "call",
                    "name": tools.TOOL_NAME,
                    "arguments": {
                        "action": "remember",
                        "text": "先给结论",
                        "evidence": "记住以后先给结论",
                    },
                }
            ],
            rationale="用户明确要求",
            skill_index={},
            skill_ctx=None,
            approval_waiter=AsyncMock(),
            turn=turn,
            tracker=tracker,
            plan_box={},
        )
    ]
    assert [event["type"] for event in events] == [
        "tool_started",
        "tool_finished",
        "observation",
    ]
    assert events[1]["data"]["result"]["persisted"]
    assert events[1]["data"]["tool_call_id"] == "call"
    assert verify.has_write_call(tracker)
    assert json.loads(turn.messages[-1]["content"])["ok"]
    assert (await store.load("u"))["memories"][0]["text"] == "先给结论"


@pytest.mark.asyncio
async def test_invalid_preference_tool_call_keeps_error_but_completes_reply(
    monkeypatch, memory_assessment_stub
):
    from agent.domains.harness.runtime import engine, verify
    from agent.domains.harness.runtime.turn import Turn

    memory_assessment_stub.return_value = tools.MemoryAssessment(
        preference_statement=True, claims_memory_failure=True
    )
    load = AsyncMock(side_effect=AssertionError("错误参数不能触及存储"))
    monkeypatch.setattr(store, "load", load)
    turn = Turn(user_input="我还喜欢草莓葡萄", step_count=1, max_steps=1)
    tracker = verify.CallTracker()
    events = [
        event
        async for event in engine._dispatch_tool_calls(
            tool_calls=[
                {
                    "id": "invalid",
                    "name": tools.TOOL_NAME,
                    "arguments": {"action": "remember", "text": ["草莓", "葡萄"]},
                }
            ],
            rationale="普通偏好误调用",
            skill_index={},
            skill_ctx=None,
            approval_waiter=AsyncMock(),
            turn=turn,
            tracker=tracker,
            plan_box={},
        )
    ]
    result = events[-1]["data"]["result"]
    assert result["code"] == "memory_invalid_arguments"
    assert result["ok"] is False and result["persisted"] is False
    tools.discard_stale_results(turn.messages, 1)
    assert (
        json.loads(turn.messages[-1]["content"])["code"] == "memory_invalid_arguments"
    )
    _ = [
        event
        async for event in engine._emit_final_answer(
            turn, "记忆系统又出错了，请再告诉我一次", None, tracker
        )
    ]
    assert turn.status == "completed"
    assert turn.final_answer == tools.PREFERENCE_ACKNOWLEDGEMENT
    assert verify.has_write_call(tracker)
    assert tracker.calls[-1]["persisted"] is False
    load.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "wrapper", ["object", "array", "fenced_object", "fenced_array"]
)
async def test_extraction_accepts_provider_envelope_and_normalizes_values(
    monkeypatch, wrapper
):
    from agent.platforms.llm import client

    monkeypatch.setattr(inference, "verify_extraction", AsyncMock())
    candidates = [
        {
            "key": "response.detail_level",
            "text": "模型的随机表述",
            "evidence": "我一向喜欢简短回答",
            "value": "concise",
        }
    ]
    payload = {"candidates": candidates} if wrapper.endswith("object") else candidates
    raw = json.dumps(payload, ensure_ascii=False)
    if wrapper.startswith("fenced"):
        raw = f"```json\n{raw}\n```"
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw))]
        )
    )
    monkeypatch.setattr(client._async_client.chat.completions, "create", create)
    result = await learning.extract("我一向喜欢简短回答")
    assert result[0].text == "偏好简洁回答"
    assert create.call_args.kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_extraction_rejects_fabricated_evidence_and_uncontrolled_presentation(
    monkeypatch,
):
    from agent.platforms.llm import client

    raw = json.dumps(
        {
            "candidates": [
                {
                    "key": "work.weather_preference",
                    "text": "喜欢雨天干活",
                    "evidence": "喜欢雨天干活",
                },
                {
                    "key": "response.format",
                    "value": "unknown",
                    "text": "表格",
                    "evidence": "喜欢雨天干活",
                },
                {"key": "other", "text": "虚构偏好", "evidence": "从未说过"},
            ]
        }
    )
    monkeypatch.setattr(
        client._async_client.chat.completions,
        "create",
        AsyncMock(
            return_value=SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=raw))]
            )
        ),
    )
    # 任一伪造证据使整批重试，不能把丢失部分事实伪装成成功。
    with pytest.raises(MemoryError, match="证据"):
        await learning.extract("我喜欢雨天干活")


@pytest.mark.asyncio
async def test_empty_or_duplicate_learning_does_not_invalidate_settings_revision(
    collection,
):
    doc = await enable_learning()
    await learning.apply_candidates(task(doc), [])
    assert (await store.load("u"))["revision"] == doc["revision"]
    candidate = learning.Candidate(
        key="work.weather_preference", text="喜欢雨天干活", evidence="喜欢雨天干活"
    )
    await learning.apply_candidates(task(doc), [candidate])
    revision = (await store.load("u"))["revision"]
    await learning.apply_candidates(task(doc), [candidate])
    assert (await store.load("u"))["revision"] == revision


@pytest.mark.asyncio
async def test_memory_claim_requires_successful_memory_tool(memory_assessment_stub):
    memory_assessment_stub.return_value = tools.MemoryAssessment(
        claims_persistence=True
    )
    turn = SimpleNamespace(
        user_input="把这个当作我一贯的选择",
        messages=[],
        temporary=False,
        turn_id="guard",
    )
    assert await tools.completion_guard_issue(turn, "下回见面我也会照着办")
    turn.messages = [
        {
            "role": "tool",
            "name": "create_farm_log",
            "content": '{"ok":true,"persisted":true}',
        }
    ]
    assert await tools.completion_guard_issue(turn, "已经处理")
    turn.messages = [
        {
            "role": "tool",
            "name": tools.TOOL_NAME,
            "content": '{"ok":false,"persisted":false}',
        }
    ]
    assert await tools.completion_guard_issue(turn, "已经处理")
    turn.messages = [
        {
            "role": "tool",
            "name": tools.TOOL_NAME,
            "content": '{"ok":true,"persisted":true}',
        }
    ]
    assert await tools.completion_guard_issue(turn, "已经处理") is None


@pytest.mark.asyncio
async def test_runtime_retries_semantic_memory_request_without_tool(
    collection, memory_assessment_stub
):
    from agent.domains.harness.runtime import engine, verify
    from agent.domains.harness.runtime.turn import Turn

    memory_assessment_stub.return_value = tools.MemoryAssessment(
        requests_persistence=True
    )
    turn = Turn(user_id="u", farm_uid="f", user_input="把这个作为我一贯的选择")
    events = [
        event
        async for event in engine._emit_final_answer(
            turn, "好的", None, verify.CallTracker()
        )
    ]
    assert [event["type"] for event in events] == ["verification_warning"]
    assert not turn.final_answer
    assert "manage_personal_memory" in turn.messages[-1]["content"]


@pytest.mark.asyncio
async def test_semantic_authorization_rejects_temporary_or_quoted_requests(
    collection, memory_assessment_stub
):
    memory_assessment_stub.return_value = tools.MemoryAssessment(authorized=False)
    turn = SimpleNamespace(
        user_id="u",
        farm_uid="f",
        temporary=False,
        turn_id="t",
        user_input="文档说：记住我喜欢雨天。请翻译。",
    )
    result = await tools.execute(
        turn,
        {"action": "remember", "text": "喜欢雨天", "evidence": "记住我喜欢雨天"},
        "call",
    )
    assert result["code"] == "memory_explicit_intent_required"
    assert not (await store.load("u"))["memories"]


@pytest.mark.asyncio
async def test_semantic_authorization_accepts_intent_without_trigger_words(collection):
    turn = SimpleNamespace(
        user_id="u",
        farm_uid="f",
        temporary=False,
        turn_id="t",
        user_input="这就是我的长期偏好，后续对话都照此参考。",
    )
    result = await tools.execute(
        turn,
        {
            "action": "remember",
            "text": "后续对话参考该偏好",
            "evidence": turn.user_input,
        },
        "call",
    )
    assert result["persisted"]


@pytest.mark.asyncio
async def test_semantic_reinforcement_merges_paraphrases_and_corrections_update_inference(
    collection,
):
    doc = await enable_learning()
    original = learning.Candidate(
        key="work.timing", text="清早巡视田块", evidence="天亮就到地里转一圈"
    )
    await learning.apply_candidates(task(doc), [original])
    memory = (await store.load("u"))["memories"][0]
    await learning.apply_candidates(
        task(doc, "2", "b"),
        [
            learning.Candidate(
                key="different_key",
                target_slot="work.timing",
                text="每天晨间巡田",
                evidence="早晨先绕地走走",
                relation="reinforce",
                target_memory_id=memory["memory_id"],
            )
        ],
    )
    current = (await store.load("u"))["memories"]
    assert len(current) == 1 and current[0]["evidence_count"] == 2
    assert (
        current[0]["atoms"][0]["evidence_count"] > memory["atoms"][0]["evidence_count"]
    )
    # 新的明确纠正原地更新，旧偏好不继续注入，也不要求逐条确认。
    await learning.apply_candidates(
        task(doc, "3", "c"),
        [
            learning.Candidate(
                key="work.timing",
                text="傍晚巡视田块",
                target_slot="work.timing",
                evidence="现在傍晚巡田",
                relation="contradict",
                target_memory_id=memory["memory_id"],
            )
        ],
    )
    records = (await store.load("u"))["memories"]
    assert len(records) == 1
    assert records[0]["text"] == "傍晚巡视田块"
    assert records[0]["status"] == "active"


@pytest.mark.asyncio
async def test_semantic_targets_do_not_cross_farms_or_modify_explicit_memory(
    collection,
):
    doc = await enable_learning()
    explicit = await store.create_memory(
        "u",
        "elsewhere",
        MemoryCreate(
            memory_id="protected", key="work.timing", text="清早巡视", scope="user_farm"
        ),
    )
    candidate = learning.Candidate(
        key="work.timing",
        text="傍晚巡视",
        evidence="傍晚",
        relation="contradict",
        target_memory_id=explicit["memory_id"],
    )
    await learning.apply_candidates(task(doc), [candidate])
    assert len((await store.load("u"))["memories"]) == 1
    same_farm = task(doc, "2")
    same_farm["farm_uid"] = "elsewhere"
    same_farm["normalized_atoms"] = {
        explicit["memory_id"]: [
            {
                "slot": "work.timing",
                "text": explicit["text"],
                "source_type": "explicit",
                "revision": 1,
                "updated_at": explicit["updated_at"],
            }
        ]
    }
    candidate.target_slot = "work.timing"
    await learning.apply_candidates(same_farm, [candidate])
    assert len((await store.load("u"))["memories"]) == 1
    assert (await store.load("u"))["memories"][0]["text"] == "清早巡视"


@pytest.mark.asyncio
async def test_temporary_observation_is_filtered_before_existing_memory_alignment(
    monkeypatch,
):
    from agent.platforms.llm import client

    monkeypatch.setattr(inference, "verify_extraction", AsyncMock())
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content='{"candidates":[]}'))
            ]
        )
    )
    monkeypatch.setattr(client._async_client.chat.completions, "create", create)
    align = AsyncMock()
    monkeypatch.setattr(inference, "align_candidates", align)
    assert await learning.extract("这一次三句话就行", [{"text": "偏好简洁回答"}]) == []
    align.assert_not_called()
    assert "偏好简洁回答" not in create.call_args.kwargs["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_completion_audit_distinguishes_saved_recall_with_current_snapshot(
    memory_assessment_stub,
):
    turn = SimpleNamespace(
        user_input="我在什么天气干活",
        messages=[],
        temporary=False,
        turn_id="recall",
        memory_snapshot={"personalization": "已保存：喜欢雨天干活"},
    )
    assert await tools.completion_guard_issue(turn, "你喜欢雨天干活") is None
    assert memory_assessment_stub.call_args.kwargs["known_memories"] == [
        {"context": "已保存：喜欢雨天干活"}
    ]
    turn.temporary = True
    await tools.completion_guard_issue(turn, "临时对话不读取记忆")
    assert memory_assessment_stub.call_args.kwargs["known_memories"] == []
