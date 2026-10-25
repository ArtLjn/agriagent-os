"""可恢复的偏好学习任务：先持久化证据，再租约消费并校验用户控制代次。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from types import SimpleNamespace

from pymongo import ReturnDocument

from agent.config import memory_runtime
from agent.domains.harness.memory.facts import (
    MAX_FACTS_PER_MEMORY,
    update_atom,
)
from agent.domains.harness.memory.inference import (
    Candidate,
    ExtractionCheck,
    align_candidates,
    extract,
    normalize_record,
    verify_extraction,
)
from agent.domains.harness.memory.personalization import (
    MAX_MEMORIES,
    MAX_MEMORY_TEXT,
    SENSITIVE_PATTERN,
    MemoryError,
    apply_business_profile,
    now,
    visible_memories,
)
from agent.platforms.persistence.mongo import personalization_store as store

logger = logging.getLogger(__name__)
# 旧 Worker 不识别原子事实，滚动发布期间必须隔离租约集合，不能只在文档加版本号。
TASK_COLLECTION = "agentMemoryLearningTasksV3"
_tasks: list[asyncio.Task] = []


def jobs():
    return store.collection().database[TASK_COLLECTION]


async def enqueue(turn) -> str:
    """将已持久化的用户消息幂等投递，返回可观测结果供消息事件确认。"""
    if turn.temporary:
        return "temporary"
    try:
        doc = await store.load(turn.user_id, memory_ids=[])
        if not doc["settings"]["auto_learn_enabled"]:
            return "disabled"
        # 以服务端接受时间阻挡关闭/重开或清空前的旧请求，也覆盖 Worker 重启恢复。
        if turn.accepted_at <= doc.get("memory_control_changed_at", 0):
            return "control_changed"
        if SENSITIVE_PATTERN.search(turn.user_input):
            return "sensitive"
        if len(turn.user_input) > memory_runtime.extraction_chars:
            return "input_too_long"  # 不截断证据，超限跳过该次抽取。
        task_id = hashlib.sha256(f"{doc['_id']}:{turn.turn_id}".encode()).hexdigest()
        await jobs().update_one(
            {"_id": task_id},
            {
                "$setOnInsert": {
                    "user_id": turn.user_id,
                    "farm_uid": turn.farm_uid,
                    "conversation_id": turn.conversation_id,
                    "turn_id": turn.turn_id,
                    "observed_at": turn.accepted_at,
                    "text": turn.user_input,
                    "generation": doc["memory_generation"],
                    "learning_generation": doc.get("learning_generation", 0),
                    "status": "pending",
                    "attempts": 0,
                    "available_at": time.time(),
                }
            },
            upsert=True,
        )
        return "queued"
    except Exception as exc:  # noqa: BLE001 -- 后台投递故障不能使已经完成的主对话失败。
        logger.warning(
            "memory enqueue unavailable code=%s",
            getattr(exc, "code", type(exc).__name__),
        )
        return "unavailable"


async def relay_observation() -> None:
    """从消息内的待投递事件恢复任务；入队后崩溃允许重放，不重新学习历史消息。"""
    from agent.platforms.persistence.mongo.chat_store import (
        MEMORY_LEARNING_EVENT,
        get_collection,
    )

    messages = get_collection()
    if messages is None:
        return
    message = await messages.find_one(
        {
            f"{MEMORY_LEARNING_EVENT}.status": "pending",
            "role": "user",
            "messageKind": "prompt",
        },
        sort=[("createdAt", 1)],
    )
    if not message:
        return
    event = message[MEMORY_LEARNING_EVENT]
    outcome = await enqueue(
        SimpleNamespace(
            temporary=False,
            user_id=message["userId"],
            farm_uid=event["farm_uid"],
            conversation_id=message["conversationId"],
            turn_id=message["turnId"],
            accepted_at=event["observed_at"],
            user_input=message["content"],
        )
    )
    if outcome != "unavailable":
        await messages.update_one(
            {"_id": message["_id"], f"{MEMORY_LEARNING_EVENT}.status": "pending"},
            {"$set": {f"{MEMORY_LEARNING_EVENT}.status": outcome}},
        )


async def learning_status(user_id: str, farm_uid: str, turn_id: str) -> dict:
    """只返回当前身份的任务进度；入队、抽取成功和实际提交必须分开表达。"""
    from agent.platforms.persistence.mongo.chat_store import (
        MEMORY_LEARNING_EVENT,
        get_collection,
    )

    task_id = hashlib.sha256(
        f"{store.owner_key(user_id)}:{turn_id}".encode()
    ).hexdigest()
    task = await jobs().find_one(
        {"_id": task_id, "user_id": user_id, "farm_uid": farm_uid},
        {"status": 1, "applied_count": 1, "reason": 1, "error_code": 1},
    )
    if task:
        return {
            "status": task["status"],
            "applied_count": task.get("applied_count", 0),
            "reason": task.get("reason"),
            "code": task.get("error_code"),
        }
    messages = get_collection()
    if messages is None:
        return {"status": "unavailable", "code": "memory_status_unavailable"}
    message = await messages.find_one(
        {
            "userId": user_id,
            "turnId": turn_id,
            "role": "user",
            f"{MEMORY_LEARNING_EVENT}.farm_uid": farm_uid,
        },
        {MEMORY_LEARNING_EVENT: 1},
    )
    event = (message or {}).get(MEMORY_LEARNING_EVENT, {})
    return {"status": event.get("status", "not_observed"), "applied_count": 0}


async def apply_candidates(task: dict, candidates: list[Candidate]) -> dict:
    """统一提交自动/显式事实；控制代次、事实修改和索引版本共用一次 CAS。"""
    identifiers = {c.target_memory_id for c in candidates if c.target_memory_id}
    for c in candidates:
        scope_id = task["farm_uid"] if c.scope == "user_farm" else "user"
        identifier = hashlib.sha256(f"{scope_id}:{c.key}".encode()).hexdigest()
        if c.target_memory_id:
            identifiers.add(
                hashlib.sha256(f"{c.target_memory_id}:{c.slot}".encode()).hexdigest()
            )
        identifiers.update(
            [identifier, hashlib.sha256(f"{identifier}:{c.text}".encode()).hexdigest()]
        )
    doc = await store.load(task["user_id"], memory_ids=list(identifiers))
    from agent.config import settings

    manifest = settings.plugins.manifest
    settings_view = apply_business_profile(
        doc,
        manifest.name if manifest else None,
        manifest.assistant_name if manifest else "",
    )
    explicit = task.get("source_type") == "explicit"
    if (
        (not explicit and not doc["settings"]["auto_learn_enabled"])
        or doc["memory_generation"] != task["generation"]
        or doc.get("learning_generation", 0) != task["learning_generation"]
    ):
        return {"applied_count": 0, "reason": "control_changed"}
    if task.get("expected_revision", doc["revision"]) != doc["revision"]:
        raise MemoryError("memory_version_conflict", "记忆已变化，重新归并")
    changed_ids = set()
    applied = 0
    for candidate in candidates:
        if (
            candidate.durability != "stable"
            or candidate.merged_text
            or SENSITIVE_PATTERN.search(candidate.text + " " + candidate.evidence)
            or ("text" in task and candidate.evidence not in task["text"])
        ):
            continue
        target = next(
            (
                m
                for m in visible_memories(doc, task["farm_uid"])
                if m["memory_id"] == candidate.target_memory_id
                and m["status"] == "active"
            ),
            None,
        )
        if candidate.relation != "new" and target is None:
            continue
        if target and target["scope"] != candidate.scope:
            raise MemoryError("memory_scope_conflict", "事实范围与目标记忆不一致")
        topic = target["key"] if target else candidate.key
        configured_key = {
            "response.detail_level": "detail_level",
            "response.format": "display_format",
            "response.style": "reply_style",
        }.get(topic, topic)
        if settings_view["field_sources"].get(configured_key) == "explicit":
            continue
        scope_id = task["farm_uid"] if candidate.scope == "user_farm" else "user"
        memory_id = (
            target["memory_id"]
            if target
            else hashlib.sha256(f"{scope_id}:{topic}".encode()).hexdigest()
        )
        record = next((m for m in doc["memories"] if m["memory_id"] == memory_id), None)
        if record and (
            record["status"] in {"deleted", "expired"}
            or (record.get("expires_at") and record["expires_at"] <= now())
        ):
            continue
        # 相同主题键也必须完成语义对齐，不能让模型换 key/slot 覆盖旧事实。
        if record and not target and memory_id not in changed_ids:
            matching = next(
                (
                    a
                    for a in record.get("atoms", [])
                    if a["slot"] == (candidate.slot or candidate.key)
                ),
                None,
            )
            if matching and matching["text"] != candidate.text:
                raise MemoryError(
                    "memory_alignment_required", "同一事实需要重新语义对齐"
                )
            if not matching:
                memory_id = hashlib.sha256(
                    f"{memory_id}:{candidate.text}".encode()
                ).hexdigest()
                record = next(
                    (m for m in doc["memories"] if m["memory_id"] == memory_id), None
                )
        # 同主题已满时扩展为另一张卡片，事实仍由 slot 索引定位，不能无限扩大单次提示。
        if (
            record
            and candidate.relation == "merge"
            and (
                len(record.get("atoms", [])) >= MAX_FACTS_PER_MEMORY
                or len(record["text"]) + len(candidate.text) + 1 > MAX_MEMORY_TEXT
            )
        ):
            memory_id = hashlib.sha256(
                f"{record['memory_id']}:{candidate.slot}".encode()
            ).hexdigest()
            record = next(
                (m for m in doc["memories"] if m["memory_id"] == memory_id), None
            )
            if record and record["status"] != "active":
                continue
            candidate = candidate.model_copy(
                update={"relation": "new", "target_slot": None}
            )
        if record is None:
            if (
                doc.get(
                    "active_memory_count",
                    sum(m["status"] == "active" for m in doc["memories"]),
                )
                >= MAX_MEMORIES
            ):
                raise MemoryError("memory_limit_reached", "记忆存储已达上限")
            record = {
                "memory_id": memory_id,
                "scope": candidate.scope,
                "farm_uid": task["farm_uid"]
                if candidate.scope == "user_farm"
                else None,
                "kind": candidate.kind,
                "category": candidate.category,
                "key": topic,
                "text": "",
                "conditions": [],
                "atoms": [],
                "source_type": "inferred",
                "status": "active",
                "revision": 0,
                "created_at": now(),
                "expires_at": None,
            }
            doc["memories"].append(record)
        if "atoms" not in record:
            atoms = task.get("normalized_atoms", {}).get(record["memory_id"])
            if not atoms:
                raise MemoryError(
                    "memory_normalization_required", "旧记忆需要先核对独立事实"
                )
            record["atoms"] = atoms
        if not update_atom(record, candidate, task):
            continue
        # 旧版分数只按轮数递增，不能继续展示为新事实的置信度。
        record.pop("confidence", None)
        turns = list(
            dict.fromkeys(
                t for a in record["atoms"] for t in a.get("evidence_turns", [])
            )
        )
        record.update(
            source_type="explicit"
            if all(a["source_type"] == "explicit" for a in record["atoms"])
            else "inferred",
            source_message_ids=[f"turn:{t}" for t in turns],
            evidence_turns=turns,
            evidence_count=len(turns),
            status="active",
            expires_at=None,
            revision=record["revision"] + 1,
            updated_at=now(),
            last_observed_at=max(a.get("last_observed_at", 0) for a in record["atoms"]),
            review_reason="按独立事实自动更新，可随时修改或删除",
        )
        changed_ids.add(memory_id)
        applied += 1
    if applied:
        await store.save(doc, doc["revision"])
    return {
        "applied_count": applied,
        "reason": "applied" if applied else "unchanged",
        "memory_ids": sorted(changed_ids),
    }


async def remember_explicit(
    turn, text: str, scope: str, *, target: dict | None = None
) -> dict:
    """显式工具完成来源核验后，复用后台的原子抽取、语义对齐和 CAS 提交。"""
    doc = await store.load(
        turn.user_id,
        **({"memory_ids": [target["memory_id"]]} if target else {"query": text}),
        farm_uid=turn.farm_uid,
    )
    existing = [
        dict(m) for m in visible_memories(doc, turn.farm_uid) if m["status"] == "active"
    ]
    if target:
        current = next(
            (m for m in existing if m["memory_id"] == target["memory_id"]), None
        )
        if not current or current["revision"] != target["revision"]:
            raise MemoryError("memory_version_conflict", "审查后目标记忆已变化")
        existing = [current]
    # 目标正文可能只删掉“喜欢葡萄”，仍需保留用户当前明确说出的“不喜欢”。
    source_text = text + "\n" + turn.user_input if target else text
    candidates = await extract(source_text)
    if not candidates:
        raise MemoryError("memory_no_durable_fact", "没有找到可保存的稳定个人事实")
    for candidate in candidates:
        candidate.scope = scope
    candidates = (
        await align_candidates(candidates, existing) if existing else candidates
    )
    if target and any(c.target_memory_id != target["memory_id"] for c in candidates):
        raise MemoryError("memory_target_mismatch", "更新内容不属于指定记忆")
    result = await apply_candidates(
        {
            "user_id": turn.user_id,
            "farm_uid": turn.farm_uid,
            "turn_id": turn.turn_id,
            "conversation_id": turn.conversation_id,
            "observed_at": turn.accepted_at,
            "text": source_text,
            "source_type": "explicit",
            "generation": doc["memory_generation"],
            "learning_generation": doc.get("learning_generation", 0),
            "expected_revision": doc["revision"],
            "normalized_atoms": {
                m["memory_id"]: m["atoms"] for m in existing if "atoms" in m
            },
        },
        candidates,
    )
    if not result["applied_count"]:
        # 成功响应丢失后同轮工具可重放；只承认已有的同轮显式事实，不能借旧事实冒充保存。
        matched = [
            m["memory_id"]
            for candidate in candidates
            for m in existing
            if candidate.relation == "reinforce"
            and m["memory_id"] == candidate.target_memory_id
            and any(
                a["slot"] == candidate.target_slot
                and a["source_type"] == "explicit"
                and turn.turn_id in a.get("evidence_turns", [])
                for a in m.get("atoms", [])
            )
        ]
        if result["reason"] == "unchanged" and len(matched) == len(candidates):
            return {
                **result,
                "reason": "already_applied",
                "memory_ids": sorted(set(matched)),
            }
        raise MemoryError("memory_not_applied", "本轮没有提交新的记忆，请查询当前状态")
    return result


async def process_one() -> bool:
    """租约过期可恢复，失败有限重试；完成后抹除任务中的用户原文。"""
    token = uuid.uuid4().hex
    current = time.time()
    await jobs().update_many(
        {
            "status": "running",
            "available_at": {"$lte": current},
            "attempts": {"$gte": memory_runtime.attempts},
        },
        {
            "$set": {"status": "failed", "error_code": "memory_lease_exhausted"},
            "$unset": {"text": ""},
        },
    )
    task = await jobs().find_one_and_update(
        {
            "status": {"$in": ["pending", "running"]},
            "available_at": {"$lte": current},
            "attempts": {"$lt": memory_runtime.attempts},
        },
        {
            "$set": {
                "status": "running",
                "lease": token,
                "available_at": current + memory_runtime.lease_seconds,
            },
            "$inc": {"attempts": 1},
        },
        return_document=ReturnDocument.AFTER,
    )
    if not task:
        return False
    try:
        control = await store.load(task["user_id"], memory_ids=[])
        if (
            control["settings"]["auto_learn_enabled"]
            and control["memory_generation"] == task["generation"]
            and control.get("learning_generation", 0) == task["learning_generation"]
        ):
            candidates = await extract(task["text"])
            existing_by_id = {}
            for candidate in candidates:
                projection = await store.load(
                    task["user_id"],
                    query=candidate.text,
                    farm_uid=task["farm_uid"],
                    keys=[candidate.key],
                    slots=[candidate.slot],
                )
                if projection["revision"] != control["revision"]:
                    raise MemoryError("memory_version_conflict", "抽取期间记忆已变化")
                existing_by_id.update(
                    {
                        m["memory_id"]: m
                        for m in visible_memories(projection, task["farm_uid"])
                        if m["status"] == "active"
                    }
                )
            # 语义索引只补充候选；命中后仍回到当前版本和授权范围，不能信任旧向量正文。
            from agent.platforms.persistence import memory_index

            semantic_ids = (
                await memory_index.retrieve(control, task["farm_uid"], task["text"])
                if candidates
                else []
            )
            if semantic_ids:
                semantic = await store.load(task["user_id"], memory_ids=semantic_ids)
                if semantic["revision"] != control["revision"]:
                    raise MemoryError(
                        "memory_version_conflict", "语义召回期间记忆已变化"
                    )
                existing_by_id.update(
                    {
                        m["memory_id"]: m
                        for m in visible_memories(semantic, task["farm_uid"])
                        if m["status"] == "active"
                    }
                )
            existing = list(existing_by_id.values())
            if candidates and existing:
                candidates = await align_candidates(candidates, existing)
            lease = await jobs().find_one(
                {
                    "_id": task["_id"],
                    "lease": token,
                    "status": "running",
                    "available_at": {"$gt": time.time()},
                }
            )
            if not lease:
                raise MemoryError(
                    "memory_lease_expired", "学习租约已过期，丢弃本次计算"
                )
            applied = await apply_candidates(
                {
                    **task,
                    "expected_revision": control["revision"],
                    "normalized_atoms": {
                        m["memory_id"]: m["atoms"] for m in existing if "atoms" in m
                    },
                },
                candidates,
            )
        else:
            candidates = []
            applied = {"applied_count": 0, "reason": "control_changed"}
        await jobs().update_one(
            {"_id": task["_id"], "lease": token},
            {
                "$set": {
                    "status": "done",
                    "candidate_count": len(candidates),
                    **applied,
                },
                "$unset": {"text": "", "error_code": ""},
            },
        )
    except Exception as exc:  # noqa: BLE001 -- 外部模型或存储故障统一进入有上限的租约重试。
        failed = task["attempts"] >= memory_runtime.attempts
        logger.warning(
            "memory learning failed code=%s task_id=%s turn_id=%s attempt=%s terminal=%s",
            getattr(exc, "code", type(exc).__name__),
            task["_id"],
            task["turn_id"],
            task["attempts"],
            failed,
        )
        update = {
            "$set": {
                "status": "failed" if failed else "pending",
                "available_at": current + memory_runtime.poll_seconds,
                "error_code": getattr(exc, "code", type(exc).__name__),
            }
        }
        if failed:
            update["$unset"] = {"text": ""}
        await jobs().update_one({"_id": task["_id"], "lease": token}, update)
    return True


async def _run(index_only: bool = False) -> None:
    from agent.platforms.persistence.memory_index import sync_one

    while True:
        try:
            if index_only:
                from agent.platforms.persistence.mongo.memory_records import (
                    collect_orphans,
                )

                await collect_orphans(store.collection())
                await sync_one()
            else:
                await relay_observation()
                await process_one()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 -- 单个任务故障不能退出常驻 Worker，取消信号已单独传播。
            logger.warning(
                "memory worker unavailable code=%s",
                getattr(exc, "code", type(exc).__name__),
            )
        await asyncio.sleep(memory_runtime.poll_seconds)


def start() -> None:
    if not _tasks:
        _tasks.extend(
            [asyncio.create_task(_run()), asyncio.create_task(_run(index_only=True))]
        )


async def stop() -> None:
    for task in _tasks:
        task.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()


__all__ = [
    "Candidate",
    "ExtractionCheck",
    "align_candidates",
    "apply_candidates",
    "enqueue",
    "extract",
    "normalize_record",
    "process_one",
    "relay_observation",
    "remember_explicit",
    "start",
    "stop",
    "verify_extraction",
]
