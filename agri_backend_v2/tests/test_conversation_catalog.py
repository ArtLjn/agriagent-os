"""草稿箱生命周期、跨租户隔离与 HTTP 访问控制回归。"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api import api_router, chat, conversations
from agent.platforms.persistence.mongo import (
    chat_store,
)
from agent.platforms.persistence.mongo import (
    conversation_catalog as catalog,
)

SCOPE = {"user_id": "u1", "farm_id": 7}
DOCUMENT = {"userId": "u1", "farmId": 7, "conversationId": "c1"}


def matches(document, where):
    for field, value in where.items():
        if isinstance(value, dict) and "$ne" in value:
            if document.get(field) == value["$ne"]:
                return False
        elif document.get(field) != value:
            return False
    return True


class Collection:
    def __init__(self, documents=()):
        self.documents = deepcopy(list(documents))

    async def find_one(self, where, _projection=None):
        return next(
            (deepcopy(doc) for doc in self.documents if matches(doc, where)), None
        )

    async def update_one(self, where, change, upsert=False):
        target = next((doc for doc in self.documents if matches(doc, where)), None)
        if target is None:
            if upsert:
                self.documents.append(deepcopy(change["$setOnInsert"]))
            return SimpleNamespace(matched_count=0)
        target.update(change.get("$set", {}))
        return SimpleNamespace(matched_count=1)


@pytest.fixture
def storage(monkeypatch):
    messages, states = Collection([DOCUMENT]), Collection()
    monkeypatch.setattr(chat_store, "get_collection", lambda: messages)
    monkeypatch.setattr(chat_store, "get_state_collection", lambda: states)
    monkeypatch.setattr(
        chat_store, "ensure_state_indexes", AsyncMock(return_value={"ok": True})
    )
    return messages, states


@pytest.mark.asyncio
async def test_archive_restore_preserves_history_and_state_revision(storage):
    messages, states = storage
    states.documents.append(
        {**DOCUMENT, "conversationRevision": 8, "summary": "历史摘要"}
    )
    result = await catalog.change_lifecycle("c1", **SCOPE, archived=True)
    assert result["archived"] is True
    assert states.documents[0]["conversationRevision"] == 8
    assert states.documents[0]["summary"] == "历史摘要"
    assert messages.documents == [DOCUMENT]
    await catalog.require_access("c1", **SCOPE)
    with pytest.raises(catalog.ConversationLifecycleError, match="恢复"):
        await catalog.require_access("c1", **SCOPE, writable=True)
    await catalog.change_lifecycle("c1", **SCOPE, archived=False)
    await catalog.require_access("c1", **SCOPE, writable=True)
    assert states.documents[0]["archivedAt"] is None


@pytest.mark.asyncio
async def test_delete_requires_archive_and_cannot_restore_or_reopen(storage):
    with pytest.raises(catalog.ConversationLifecycleError) as error:
        await catalog.change_lifecycle("c1", **SCOPE, delete=True)
    assert error.value.code == "conversation_not_archived"
    await catalog.change_lifecycle("c1", **SCOPE, archived=True)
    await catalog.change_lifecycle("c1", **SCOPE, delete=True)
    assert (await catalog.change_lifecycle("c1", **SCOPE, delete=True))["deleted"]
    for writable in (True, False):
        with pytest.raises(catalog.ConversationLifecycleError) as error:
            await catalog.require_access("c1", **SCOPE, writable=writable)
        assert error.value.status_code == 404
    with pytest.raises(catalog.ConversationLifecycleError):
        await catalog.change_lifecycle("c1", **SCOPE, archived=False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scope", [{"user_id": "other", "farm_id": 7}, {"user_id": "u1", "farm_id": 8}]
)
async def test_archive_and_delete_do_not_cross_owner_or_farm(storage, scope):
    _, states = storage
    states.documents.append({**DOCUMENT, "archived": True})
    for options in ({"archived": True}, {"archived": False}, {"delete": True}):
        with pytest.raises(catalog.ConversationLifecycleError) as error:
            await catalog.change_lifecycle("c1", **scope, **options)
        assert error.value.status_code == 404
    assert states.documents == [{**DOCUMENT, "archived": True}]


@pytest.mark.asyncio
async def test_delete_wins_against_inflight_restore(storage, monkeypatch):
    _, states = storage
    await catalog.change_lifecycle("c1", **SCOPE, archived=True)
    original = states.update_one

    async def delete_first(where, change, **kwargs):
        states.documents[0]["lifecycle"] = catalog.DELETED
        return await original(where, change, **kwargs)

    monkeypatch.setattr(states, "update_one", delete_first)
    with pytest.raises(catalog.ConversationLifecycleError) as error:
        await catalog.change_lifecycle("c1", **SCOPE, archived=False)
    assert error.value.code == "conversation_state_changed"
    assert states.documents[0]["lifecycle"] == catalog.DELETED


@pytest.mark.asyncio
async def test_storage_failure_is_not_reported_as_success_or_empty(
    storage, monkeypatch
):
    messages, states = storage
    monkeypatch.setattr(
        states, "update_one", AsyncMock(side_effect=RuntimeError("含凭据的连接信息"))
    )
    with pytest.raises(catalog.ConversationLifecycleError) as error:
        await catalog.change_lifecycle("c1", **SCOPE, archived=True)
    assert error.value.status_code == 503
    assert "凭据" not in str(error.value)
    monkeypatch.setattr(chat_store, "get_collection", lambda: None)
    with pytest.raises(catalog.ConversationLifecycleError):
        await catalog.list_conversations(**SCOPE)
    assert messages.documents == [DOCUMENT]


@pytest.mark.asyncio
@pytest.mark.parametrize("archived", [True, False])
async def test_list_filters_state_with_same_tenant_before_limit(storage, archived):
    messages, _ = storage
    captured = []

    def aggregate(pipeline):
        captured.extend(pipeline)
        return SimpleNamespace(to_list=AsyncMock(return_value=[]))

    messages.aggregate = aggregate
    await catalog.list_conversations(limit=2, **SCOPE, archived=archived)
    assert captured[0] == {"$match": {"userId": "u1", "farmId": 7}}
    join = next(stage["$lookup"] for stage in captured if "$lookup" in stage)
    assert join["pipeline"][0]["$match"] == {
        "userId": "u1",
        "farmId": 7,
        "$expr": {"$eq": ["$conversationId", "$$conversation"]},
    }
    filters = next(
        stage["$match"]
        for stage in captured
        if "catalog.lifecycle" in stage.get("$match", {})
    )
    assert filters == {
        "catalog.lifecycle": {"$ne": "deleted"},
        "catalog.archived": True if archived else {"$ne": True},
    }
    assert captured[-1] == {"$limit": 3}


def test_api_permissions_validation_and_deleted_links(storage, monkeypatch):
    app = FastAPI()
    app.include_router(api_router)
    identity = {
        **SCOPE,
        "role": "user",
        "farm_uid": "farm",
        "scope": "conversation:read conversation:write agent:invoke",
    }
    with TestClient(app) as client:
        path = "/api/v2/conversations/c1"
        assert client.patch(path, json={"archived": True}).status_code == 401
        monkeypatch.setattr(conversations, "parse_identity", lambda _: identity)
        monkeypatch.setattr(chat, "parse_identity", lambda _: identity)
        assert client.patch(path, json={"archived": "true"}).status_code == 422
        assert (
            client.patch(path, json={"archived": True, "user_id": "other"}).status_code
            == 422
        )
        identity["scope"] = "conversation:read"
        assert client.patch(path, json={"archived": True}).status_code == 403
        assert client.delete(path).status_code == 403
        identity["scope"] += " conversation:write agent:invoke"
        assert client.delete(path).status_code == 409
        assert client.patch(path, json={"archived": True}).status_code == 200
        assert (
            client.post(
                "/api/v2/chat", json={"conversation_id": "c1", "message": "继续"}
            ).status_code
            == 409
        )
        assert client.delete(path).status_code == 200
        assert client.delete(path).status_code == 200
        for suffix in ("", "/messages", "/turns", "/turns/t1"):
            response = client.get(path + suffix)
            assert response.status_code == 404, response.text
            assert response.json()["detail"]["code"] == "conversation_not_found"
        assert (
            client.post(
                "/api/v2/chat", json={"conversation_id": "c1", "message": "继续"}
            ).status_code
            == 404
        )
