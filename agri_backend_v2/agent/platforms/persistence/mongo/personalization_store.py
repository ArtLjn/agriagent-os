"""个人配置原子存储：单文档 CAS 保护设置、明确记忆与清空操作。"""

from __future__ import annotations

import time
from copy import deepcopy

from pymongo.errors import DuplicateKeyError, PyMongoError

from agent.config import settings
from agent.domains.harness.memory.personalization import (
    COLLECTION_NAME,
    MAX_MEMORIES,
    MemoryCreate,
    MemoryError,
    MemoryPatch,
    Settings,
    SettingsPatch,
    new_document,
    now,
    reject_sensitive_text,
)
from agent.platforms.persistence.mongo import chat_store


def owner_key(user_id: str) -> str:
    """JWT issuer 与 subject 共同确定身份，避免跨签发域复用用户 ID。"""
    return f"{settings.auth.jwt_issuer}:{user_id}"


def collection():
    source = chat_store.get_collection()
    if source is None:
        raise MemoryError("memory_storage_unavailable", "记忆存储暂不可用", 503)
    return source.database[COLLECTION_NAME]


async def load(user_id: str) -> dict:
    """存储故障必须与没有配置区分，禁止将故障伪装为空记录。"""
    try:
        owner = owner_key(user_id)
        return await collection().find_one({"_id": owner}) or new_document(owner)
    except PyMongoError as exc:
        raise MemoryError(
            "memory_storage_unavailable", "记忆存储暂不可用", 503
        ) from exc


async def save(document: dict, expected: int) -> dict:
    """首次写入利用主键唯一约束，其余写入通过版本条件原子替换。"""
    document = deepcopy(document)
    document.update(revision=expected + 1, updated_at=now(), index_pending=True)
    try:
        coll = collection()
        if expected == 0:
            await coll.insert_one(document)
        else:
            result = await coll.replace_one(
                {"_id": document["_id"], "revision": expected}, document
            )
            if result.matched_count != 1:
                raise MemoryError("memory_version_conflict", "设置已变化，请重新加载")
    except DuplicateKeyError as exc:
        raise MemoryError("memory_version_conflict", "设置已变化，请重新加载") from exc
    except PyMongoError as exc:
        raise MemoryError("memory_storage_unavailable", "记忆保存失败", 503) from exc
    return document


async def update_settings(user_id: str, patch: SettingsPatch) -> dict:
    """设置页和后续对话工具共用此入口，显式偏好只维护一份。"""
    doc = await load(user_id)
    if doc["revision"] != patch.expected_revision:
        raise MemoryError("memory_version_conflict", "设置已变化，请重新加载")
    changes = patch.model_dump(exclude_unset=True, exclude={"expected_revision"})
    if (
        "auto_learn_enabled" in changes
        and changes["auto_learn_enabled"] != doc["settings"]["auto_learn_enabled"]
    ):
        doc["learning_generation"] = doc.get("learning_generation", 0) + 1
        doc["memory_control_changed_at"] = time.time()
    for key in ("nickname", "assistant_name", "custom_instructions"):
        if key in changes:
            reject_sensitive_text(changes[key])
    doc["settings"] = Settings.model_validate(
        {**doc["settings"], **changes}
    ).model_dump()
    doc["field_sources"].update({key: "explicit" for key in changes})
    return await save(doc, patch.expected_revision)


async def create_memory(user_id: str, farm_uid: str, request: MemoryCreate) -> dict:
    """客户端稳定 ID 提供重试幂等性；农场归属只能由认证身份传入。"""
    reject_sensitive_text(request.text + " " + " ".join(request.conditions))
    doc = await load(user_id)
    for existing in doc["memories"]:
        if existing["memory_id"] == request.memory_id:
            if existing["status"] == "deleted":
                raise MemoryError("memory_deleted", "该记忆已删除，请使用新的标识")
            fields = request.model_dump()
            if any(existing[k] != v for k, v in fields.items()) or (
                request.scope == "user_farm" and existing["farm_uid"] != farm_uid
            ):
                raise MemoryError("memory_id_conflict", "记忆标识已被使用")
            return existing
    if request.key in Settings.model_fields or request.key.startswith("response."):
        raise MemoryError("memory_reserved_key", "表达设置请通过个性化配置更新", 422)
    if any(
        m["status"] == "active"
        and m["scope"] == request.scope
        and m.get("farm_uid") == (farm_uid if request.scope == "user_farm" else None)
        and m["key"] == request.key
        and m["conditions"] == request.conditions
        for m in doc["memories"]
    ):
        raise MemoryError("memory_key_conflict", "该偏好已存在，请编辑已有记忆")
    if (
        sum(
            m["status"] not in {"deleted", "expired"}
            and (not m.get("expires_at") or m["expires_at"] > now())
            for m in doc["memories"]
        )
        >= MAX_MEMORIES
    ):
        raise MemoryError("memory_limit_reached", "记忆存储已达上限", 422)
    timestamp = now()
    record = {
        **request.model_dump(),
        "farm_uid": farm_uid if request.scope == "user_farm" else None,
        "source_type": "explicit",
        "source_message_ids": [],
        "evidence_count": 1,
        "status": "active",
        "expires_at": None,
        "revision": 1,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    doc["memories"].append(record)
    await save(doc, doc["revision"])
    return record


async def modify_memory(
    user_id: str, farm_uid: str, memory_id: str, patch: MemoryPatch | None = None
) -> dict:
    """更新和删除都限定当前可见范围，删除正文仅留下最小重试屏障。"""
    doc = await load(user_id)
    record = next(
        (
            m
            for m in doc["memories"]
            if m["memory_id"] == memory_id
            and (m["scope"] == "user" or m.get("farm_uid") == farm_uid)
        ),
        None,
    )
    if record is None:
        raise MemoryError("memory_not_found", "记忆不存在", 404)
    if record["status"] == "deleted":
        if patch is None:
            return record
        raise MemoryError("memory_not_found", "记忆不存在", 404)
    if patch is None:
        doc["memory_generation"] += 1
        doc["memory_control_changed_at"] = time.time()
        record.update(
            status="deleted", text="", conditions=[], key="", source_message_ids=[]
        )
    else:
        if patch.expected_revision != record["revision"]:
            raise MemoryError("memory_version_conflict", "记忆已变化，请重新加载")
        record.update(
            patch.model_dump(exclude_unset=True, exclude={"expected_revision"})
        )
        reject_sensitive_text(record["text"] + " " + " ".join(record["conditions"]))
        record["source_type"] = "explicit"
        record["expires_at"] = None
        if "text" in patch.model_fields_set and "status" not in patch.model_fields_set:
            record["status"] = "active"
    record.update(revision=record["revision"] + 1, updated_at=now())
    await save(doc, doc["revision"])
    return record


async def clear_memories(user_id: str, farm_uid: str) -> dict:
    """清空本人全部个人记忆；主键约束保证不影响其他用户和手工配置。"""
    doc = await load(user_id)
    records = [m for m in doc["memories"] if m["status"] != "deleted"]
    for record in records:
        record.update(
            status="deleted",
            text="",
            key="",
            conditions=[],
            source_message_ids=[],
            revision=record["revision"] + 1,
            updated_at=now(),
        )
    doc["memory_generation"] += 1
    doc["memory_control_changed_at"] = time.time()
    await save(doc, doc["revision"])
    return {"cleared": len(records), "memory_generation": doc["memory_generation"]}
