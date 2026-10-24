"""大规模记忆正文存储：不可变记录先写入，再以用户清单 CAS 原子发布。

兼容无事务的单节点 Mongo。清单只保存引用，未成功发布的正文不可被检索；
读取始终按当前清单过滤，删除后的旧正文由提交路径和回收任务清理。
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from copy import deepcopy

from agent.domains.harness.memory.facts import query_terms, searchable_text
from agent.domains.harness.memory.personalization import MAX_MEMORIES, MemoryError, now

COLLECTION = "agentMemoryRecordsV3"
INLINE_LIMIT = 200
RETRIEVAL_LIMIT = 60
GC_GRACE_SECONDS = 300
MAX_MANIFEST_BYTES = 12 * 1024 * 1024
_indexed_databases: set[str] = set()


def fingerprint(record):
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


async def ensure_indexes(root):
    """检索从租户和词项索引进入，避免把全部正文带回 Agent。"""
    name = root.database.name
    if name in _indexed_databases:
        return
    records = root.database[COLLECTION]
    for field in ("terms", "slots", "key", "index_id"):
        await records.create_index([("owner", 1), (field, 1)])
    await records.create_index([("created_at", 1)])
    _indexed_databases.add(name)


def rank_records(
    records, *, query="", keys=(), slots=(), ids=(), limit=RETRIEVAL_LIMIT
):
    """旧内嵌数据使用有界堆选取，同一规则兼容迁移前读取。"""
    import heapq

    terms = query_terms(query)
    key_set, slot_set, id_set = set(keys), set(slots), set(ids)

    def score(record):
        return (
            record["memory_id"] in id_set,
            bool(slot_set & {a["slot"] for a in record.get("atoms", [])}),
            record.get("key") in key_set,
            len(terms & query_terms(searchable_text(record))),
            record.get("updated_at", ""),
        )

    matches = (
        r
        for r in records
        if not (query or keys or slots or ids)
        or any(score(r)[:4])
        or r.get("category") == "response"
    )
    return heapq.nlargest(limit, matches, key=score)


async def hydrate(
    root,
    document,
    *,
    ids=None,
    query=None,
    farm_uid=None,
    keys=(),
    slots=(),
    limit=RETRIEVAL_LIMIT,
):
    """查询仅能命中已发布版本；按条件过滤后在数据库中排序和限制返回量。"""
    references = document.get("memory_refs")
    if references is None and document.get("storage_version") != 3:
        return document
    records = root.database[COLLECTION]
    where = {"owner": document["_id"]}
    if references is None:
        document["_partial_refs"] = True
        if ids is not None:
            projected = {
                "revision": 1,
                **{f"memory_refs.{identifier}": 1 for identifier in ids},
            }
            head = await root.find_one({"_id": document["_id"]}, projected)
            references = (head or {}).get("memory_refs", {})
    if references is not None:
        selected = (
            [references[i] for i in ids if i in references]
            if ids is not None
            else list(references.values())
        )
        where["_id"] = {"$in": selected}
    if farm_uid is not None:
        where["$or"] = [{"scope": "user"}, {"scope": "user_farm", "farm_uid": farm_uid}]
    if query is not None:
        import asyncio

        where["status"] = "active"
        where["$nor"] = [{"record.expires_at": {"$lte": now(), "$type": "string"}}]
        found = []
        # 精确身份先走独立索引，不与高频词 OR 后再做全用户排序。
        for field, values in (("slots", slots), ("key", keys)):
            if values:
                found = (
                    await records.find(
                        {**where, field: {"$in": list(values)}}, {"record": 1}
                    )
                    .hint([("owner", 1), (field, 1)])
                    .limit(limit)
                    .to_list(length=limit)
                )
                if found:
                    break
        if not found and not query and not keys and not slots:
            found = (
                await records.find(where, {"record": 1})
                .sort("record.updated_at", -1)
                .limit(limit)
                .to_list(length=limit)
            )
        if not found:
            # 高频词只参与最终排序，稀有词负责产生有界候选；计数到候选上限即停止。
            terms = sorted(query_terms(query), key=lambda term: (-len(term), term))[:12]
            probe = {k: v for k, v in where.items() if k != "_id"}
            counts = await asyncio.gather(
                *(
                    records.count_documents(
                        {**probe, "terms": term},
                        limit=limit + 1,
                        hint=[("owner", 1), ("terms", 1)],
                    )
                    for term in terms
                )
            )
            ranked_terms = sorted(
                (count, term) for count, term in zip(counts, terms) if count
            )
            rare = [
                term for count, term in ranked_terms if count <= ranked_terms[0][0] * 2
            ][:3]
            if rare:
                found = (
                    await records.find({**where, "terms": {"$in": rare}}, {"record": 1})
                    .hint([("owner", 1), ("terms", 1)])
                    .limit(limit * 4)
                    .to_list(length=limit * 4)
                )
            else:
                found = (
                    await records.find({**where, "category": "response"}, {"record": 1})
                    .limit(limit)
                    .to_list(length=limit)
                )
    else:
        found = await records.find(where, {"record": 1}).to_list(length=None)
    if document.get("_partial_refs"):
        projected = {
            "revision": 1,
            **{f"memory_refs.{r['record']['memory_id']}": 1 for r in found},
        }
        head = await root.find_one({"_id": document["_id"]}, projected)
        if not head or head["revision"] != document["revision"]:
            raise MemoryError("memory_version_conflict", "读取期间记忆已变化")
        references = head.get("memory_refs", {})
        # 查询候选可能包含尚未发布或已被替换的版本，必须回到当前清单核对。
        found = [
            r for r in found if r.get("_id") == references.get(r["record"]["memory_id"])
        ]
        document["memory_refs"] = references
    if query is None and references is not None and len(found) != len(selected):
        raise MemoryError(
            "memory_storage_incomplete", "记忆正文暂不可用，不能视为空记录", 503
        )
    document["memories"] = [r["record"] for r in found]
    if query is not None:
        document["memories"] = rank_records(
            document["memories"], query=query, keys=keys, slots=slots, limit=limit
        )
    document["_loaded_hashes"] = {
        m["memory_id"]: fingerprint(m) for m in document["memories"]
    }
    return document


async def save(root, document, expected):
    """仅写变更正文，旧值在清单 CAS 成功前仍有效；失败时撤销本次未发布副本。"""
    await ensure_indexes(root)
    records = root.database[COLLECTION]
    references = dict(document.get("memory_refs", {}))
    if document.pop("_partial_refs", False):
        current = await root.find_one({"_id": document["_id"]})
        if not current or current["revision"] != expected:
            raise MemoryError("memory_version_conflict", "记忆已变化，请重新加载")
        references = dict(current["memory_refs"])
    hashes = document.get("_loaded_hashes", {})
    inserted, obsolete = [], []
    for record in document["memories"]:
        identifier = record["memory_id"]
        if identifier in references and hashes.get(identifier) == fingerprint(record):
            continue
        blob_id = uuid.uuid4().hex
        inserted.append(
            {
                "_id": blob_id,
                "owner": document["_id"],
                "memory_id": identifier,
                "record": deepcopy(record),
                "status": record["status"],
                "scope": record["scope"],
                "farm_uid": record.get("farm_uid"),
                "key": record["key"],
                "category": record.get("category", "general"),
                "terms": sorted(query_terms(searchable_text(record))),
                "slots": [a["slot"] for a in record.get("atoms", [])],
                "created_at": time.time(),
                "base_revision": expected,
                "index_id": hashlib.sha256(
                    f"{document['_id']}:{identifier}:{record['revision']}".encode()
                ).hexdigest(),
            }
        )
        if identifier in references:
            obsolete.append(references[identifier])
        references[identifier] = blob_id
    published = {
        k: v for k, v in document.items() if k not in {"memories", "_loaded_hashes"}
    }
    published.update(memory_refs=references, storage_version=3)
    try:
        if inserted:
            await records.insert_many(inserted)
        published["active_memory_count"] = await records.count_documents(
            {
                "owner": document["_id"],
                "_id": {"$in": list(references.values())},
                "status": "active",
                "$nor": [{"record.expires_at": {"$lte": now(), "$type": "string"}}],
            }
        )
        if published["active_memory_count"] > MAX_MEMORIES:
            raise MemoryError("memory_limit_reached", "记忆存储已达上限")
        from bson import BSON

        if len(BSON.encode(published)) > MAX_MANIFEST_BYTES:
            raise MemoryError("memory_manifest_limit", "记忆版本清单已达容量上限")
        if expected == 0:
            await root.insert_one(published)
        else:
            result = await root.replace_one(
                {"_id": document["_id"], "revision": expected}, published
            )
            if result.matched_count != 1:
                raise MemoryError("memory_version_conflict", "记忆已变化，请重新加载")
    except MemoryError:
        # 已知 CAS 失败可以撤销；网络超时结果不明时保留，交给带发布检查的回收任务。
        if inserted:
            await records.delete_many({"_id": {"$in": [r["_id"] for r in inserted]}})
        raise
    if obsolete:
        from pymongo.errors import PyMongoError

        try:
            await records.delete_many(
                {"owner": document["_id"], "_id": {"$in": obsolete}}
            )
        except PyMongoError:
            logging.getLogger(__name__).warning(
                "memory cleanup deferred code=memory_gc_pending"
            )
    document["active_memory_count"] = published["active_memory_count"]
    document["memory_refs"] = references
    document["storage_version"] = 3
    document["_loaded_hashes"] = {
        m["memory_id"]: fingerprint(m) for m in document["memories"]
    }
    return document


async def collect_orphans(root):
    """崩溃恢复仅删除超过宽限期且不被当前清单引用的正文。"""
    records = root.database[COLLECTION]
    cursor = (
        records.find({"created_at": {"$lt": time.time() - GC_GRACE_SECONDS}})
        .sort("checked_at", 1)
        .limit(100)
    )
    async for record in cursor:
        head = await root.find_one(
            {"_id": record["owner"]},
            {"revision": 1, f"memory_refs.{record['memory_id']}": 1},
        )
        if (head or {}).get("revision", 0) > record.get("base_revision", 0) and record[
            "_id"
        ] not in (head or {}).get("memory_refs", {}).values():
            await records.delete_one({"_id": record["_id"]})
        else:
            await records.update_one(
                {"_id": record["_id"]}, {"$set": {"checked_at": time.time()}}
            )
