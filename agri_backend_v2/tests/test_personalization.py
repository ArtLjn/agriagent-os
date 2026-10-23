"""个性化隔离、原子更新、删除与上下文边界回归。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError
from pymongo.errors import DuplicateKeyError

from agent.domains.harness.memory.personalization import (
    MemoryCreate,
    MemoryError,
    MemoryPatch,
    SettingsPatch,
    context_text,
    visible_memories,
)
from agent.platforms.persistence.mongo import personalization_store as store
from agent.domains.harness.context import builder


class Collection:
    def __init__(self):
        self.docs = {}

    async def find_one(self, query):
        return deepcopy(self.docs.get(query["_id"]))

    async def insert_one(self, doc):
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("重复")
        self.docs[doc["_id"]] = deepcopy(doc)

    async def replace_one(self, query, doc):
        old = self.docs.get(query["_id"])
        matched = old is not None and old["revision"] == query["revision"]
        if matched:
            self.docs[doc["_id"]] = deepcopy(doc)
        return SimpleNamespace(matched_count=int(matched))


@pytest.fixture
def collection(monkeypatch):
    coll = Collection()
    monkeypatch.setattr(store, "collection", lambda: coll)
    return coll


@pytest.mark.asyncio
async def test_settings_cas_and_user_isolation(collection):
    initial = await store.load("a")
    saved = await store.update_settings(
        "a", SettingsPatch(expected_revision=0, nickname="农友")
    )
    assert saved["revision"] == 1
    assert (await store.load("b"))["settings"]["nickname"] == ""
    with pytest.raises(MemoryError, match="变化"):
        await store.save(initial, 0)
    with pytest.raises(MemoryError, match="变化"):
        await store.update_settings(
            "a", SettingsPatch(expected_revision=0, nickname="旧值")
        )
    assert (await store.load("a"))["settings"]["nickname"] == "农友"


@pytest.mark.asyncio
async def test_memory_scope_idempotency_delete_and_clear(collection):
    req = MemoryCreate(
        memory_id="one", key="cost.preference", text="成本先看异常", scope="user_farm"
    )
    record = await store.create_memory("a", "farm-a", req)
    assert await store.create_memory("a", "farm-a", req) == record
    assert not visible_memories(await store.load("a"), "farm-b")
    with pytest.raises(MemoryError):
        await store.modify_memory("a", "farm-b", "one")
    with pytest.raises(MemoryError):
        await store.modify_memory("b", "farm-a", "one")
    await store.modify_memory(
        "a", "farm-a", "one", MemoryPatch(expected_revision=1, text="先看利润")
    )
    with pytest.raises(MemoryError):
        await store.modify_memory(
            "a", "farm-a", "one", MemoryPatch(expected_revision=1, text="旧值")
        )
    await store.modify_memory("a", "farm-a", "one")
    await store.modify_memory("a", "farm-a", "one")
    with pytest.raises(MemoryError):
        await store.create_memory("a", "farm-a", req)
    assert "先看利润" not in str(await store.load("a"))
    result = await store.clear_memories("a", "farm-a")
    assert result["memory_generation"] == 2
    assert (await store.load("a"))["settings"]["assistant_name"] == "田掌柜"


@pytest.mark.asyncio
async def test_context_keeps_user_authority_and_read_switch(collection):
    await store.create_memory(
        "a", "farm", MemoryCreate(memory_id="one", key="cost", text="成本先看异常")
    )
    doc = await store.load("a")
    assert "成本先看异常" in context_text(doc, "farm")
    doc = await store.update_settings(
        "a", SettingsPatch(expected_revision=doc["revision"], use_saved_memories=False)
    )
    text = context_text(doc, "farm")
    assert "成本先看异常" not in text
    bundle = builder.build_context_bundle("你好", {"personalization": text})
    messages = builder.bundle_to_messages(bundle)
    assert any(m["role"] == "user" and m["content"] == text for m in messages)
    assert not any(m["role"] == "system" and m["content"] == text for m in messages)


@pytest.mark.parametrize(
    "payload",
    [
        {"expected_revision": 0, "user_id": "other"},
        {"expected_revision": 0, "auto_learn_enabled": "true"},
        {"expected_revision": 0, "reply_style": "unknown"},
        {"expected_revision": 0, "nickname": None},
    ],
)
def test_invalid_settings_rejected(payload):
    with pytest.raises(ValidationError):
        SettingsPatch.model_validate(payload)


@pytest.mark.asyncio
async def test_api_auth_validation_and_failure(monkeypatch):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from agent.api import api_router
    from agent.api import personalization as api

    app = FastAPI()
    app.include_router(api_router)
    async with AsyncClient(
        transport=ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v2/me/personalization")
        assert response.status_code in (401, 503)
        monkeypatch.setattr(
            api, "parse_identity", lambda _: {"user_id": "a", "farm_uid": "f"}
        )
        monkeypatch.setattr(
            api, "require_identity_permission", lambda principal, _: principal
        )
        monkeypatch.setattr(
            store,
            "load",
            AsyncMock(
                side_effect=MemoryError("memory_storage_unavailable", "不可用", 503)
            ),
        )
        response = await client.get("/api/v2/me/personalization")
        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "memory_storage_unavailable"
        response = await client.patch(
            "/api/v2/me/personalization", json={"expected_revision": 0, "user_id": "b"}
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_duplicate_key_and_storage_failure(collection, monkeypatch):
    from pymongo.errors import ServerSelectionTimeoutError
    from agent.domains.harness.memory.long_term import get_personalization_context

    await store.create_memory(
        "a", "farm", MemoryCreate(memory_id="first", key="cost", text="先看成本")
    )
    with pytest.raises(MemoryError) as error:
        await store.create_memory(
            "a", "farm", MemoryCreate(memory_id="second", key="cost", text="先看利润")
        )
    assert error.value.code == "memory_key_conflict"
    collection.find_one = AsyncMock(side_effect=ServerSelectionTimeoutError("离线"))
    with pytest.raises(MemoryError) as error:
        await store.load("a")
    assert error.value.status == 503
    assert await get_personalization_context(user_id="a", farm_uid="farm") == {}


def test_memory_patch_cannot_clear_required_values():
    with pytest.raises(ValidationError):
        MemoryPatch(expected_revision=1, text=None)
    with pytest.raises(ValidationError):
        MemoryCreate(memory_id="id", key="cost", text="测试", conditions=["x" * 101])
