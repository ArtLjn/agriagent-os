"""QuillRAG 记忆索引适配；Mongo 主数据验证是唯一可见性依据。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from urllib.parse import quote

import httpx
from pymongo import ReturnDocument

from agent.config import memory_runtime as cfg
from agent.domains.harness.memory.personalization import now, visible_memories
from agent.platforms.persistence.mongo import personalization_store as store

logger = logging.getLogger(__name__)
MANIFEST_COLLECTION = "agentMemoryIndexManifest"


def doc_id(owner: str, record: dict) -> str:
    return hashlib.sha256(
        f"{owner}:{record['memory_id']}:{record['revision']}".encode()
    ).hexdigest()


def client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=cfg.rag_url.rstrip("/"),
        timeout=timeout,
        headers={"X-API-Key": cfg.rag_api_key},
    )


async def retrieve(document: dict, farm_uid: str, query: str) -> list[str]:
    """全局与农场范围分别过滤，返回 ID 后仍必须回查权威版本。"""
    if not cfg.rag_url or not cfg.rag_api_key or not query:
        return []
    try:
        async with (
            asyncio.timeout(cfg.retrieve_timeout),
            client(cfg.retrieve_timeout) as http,
        ):
            results = await asyncio.gather(
                *[
                    http.post(
                        "/retrieve",
                        json={
                            "collection": cfg.rag_collection,
                            "query": query,
                            "top_k": 10,
                            "mode": "hybrid",
                            "rerank": False,
                            "use_hyde": False,
                            "filters": {
                                "owner": document["_id"],
                                "scope": scope,
                                **extra,
                            },
                        },
                    )
                    for scope, extra in [
                        ("user", {}),
                        ("user_farm", {"farm_uid": farm_uid}),
                    ]
                ]
            )
            authoritative = document
            if document.get("_partial_inline"):
                # 旧内嵌模式正文最多 200 条；部分投影不能用来否决索引命中的其他有效记录。
                authoritative = await store.collection().find_one(
                    {"_id": document["_id"]}
                ) or {"memories": []}
            valid = {
                doc_id(document["_id"], m): m["memory_id"]
                for m in visible_memories(authoritative, farm_uid)
                if m["status"] == "active"
            }
            if "memory_refs" in document:
                from agent.platforms.persistence.mongo.memory_records import COLLECTION

                hit_ids = [
                    hit.get("doc_id")
                    for response in results
                    for hit in response.json().get("data", {}).get("results", [])
                ]
                cursor = (
                    store.collection()
                    .database[COLLECTION]
                    .find(
                        {
                            "owner": document["_id"],
                            "index_id": {"$in": hit_ids},
                            "status": "active",
                            "$or": [
                                {"scope": "user"},
                                {"scope": "user_farm", "farm_uid": farm_uid},
                            ],
                        }
                    )
                )
                hits = [r async for r in cursor]
                head = await store.collection().find_one(
                    {"_id": document["_id"]},
                    {
                        "revision": 1,
                        **{f"memory_refs.{r['memory_id']}": 1 for r in hits},
                    },
                )
                references = (head or {}).get("memory_refs", {})
                valid.update(
                    {
                        r["index_id"]: r["memory_id"]
                        for r in hits
                        if r["_id"] == references.get(r["memory_id"])
                    }
                )
            ids = []
            for response in results:
                response.raise_for_status()
                body = response.json()
                if body.get("code") != "OK":
                    raise ValueError("memory_retrieve_failed")
                for hit in body.get("data", {}).get("results", []):
                    if hit.get("doc_id") in valid:
                        ids.append(valid[hit["doc_id"]])
            return list(dict.fromkeys(ids))
    except (TimeoutError, httpx.HTTPError, ValueError):
        logger.warning(
            "memory semantic retrieval fallback code=memory_retrieve_unavailable"
        )
        return []


async def sync_one() -> None:
    """先登记版本文档再上传；崩溃遗留的版本可通过清单重试或删除。"""
    if not cfg.rag_url or not cfg.rag_api_key:
        return
    coll = store.collection()
    manifest = coll.database[MANIFEST_COLLECTION]
    document = await coll.find_one_and_update(
        {
            "index_pending": True,
            "$or": [
                {"index_available_at": {"$exists": False}},
                {"index_available_at": {"$lte": time.time()}},
            ],
        },
        {"$set": {"index_available_at": time.time() + cfg.lease_seconds}},
        return_document=ReturnDocument.AFTER,
    )
    async with client(cfg.index_timeout) as http:
        if document:
            from agent.platforms.persistence.mongo.memory_records import hydrate

            document = await hydrate(coll, document)
            # QuillRAG 入库不会自动建集合；独立集合创建接口本身幂等。
            created = await http.post("/collections", json={"name": cfg.rag_collection})
            created.raise_for_status()
            if created.json().get("code") != "OK":
                raise ValueError("memory_collection_unavailable")
            indexed = 0
            finished = True
            for record in document["memories"]:
                if record["status"] != "active" or (
                    record.get("expires_at") and record["expires_at"] <= now()
                ):
                    continue
                identifier = doc_id(document["_id"], record)
                existing = await manifest.find_one({"_id": identifier})
                if existing and existing["status"] == "ready":
                    continue
                if indexed >= cfg.index_batch_size:
                    finished = False
                    break
                indexed += 1
                await manifest.update_one(
                    {"_id": identifier},
                    {
                        "$setOnInsert": {
                            "owner": document["_id"],
                            "memory_id": record["memory_id"],
                            "revision": record["revision"],
                            "status": "pending",
                        }
                    },
                    upsert=True,
                )
                response = await http.post(
                    "/ingest",
                    data={
                        "collection": cfg.rag_collection,
                        "text": record["text"],
                        "doc_id": identifier,
                        "strategy": "fixed",
                        "chunk_size": "4000",
                        "chunk_overlap": "0",
                        "metadata_json": json.dumps(
                            {
                                "owner": document["_id"],
                                "memory_id": record["memory_id"],
                                "revision": record["revision"],
                                "scope": record["scope"],
                                "farm_uid": record.get("farm_uid"),
                            }
                        ),
                    },
                )
                response.raise_for_status()
                if response.json().get("code") != "OK":
                    raise ValueError("memory_index_failed")
                await manifest.update_one(
                    {"_id": identifier}, {"$set": {"status": "ready"}}
                )
            await coll.update_one(
                {"_id": document["_id"], "revision": document["revision"]},
                {
                    "$set": {
                        "index_pending": not finished,
                        "index_available_at": time.time(),
                        "indexed_revision": document["revision"],
                    }
                },
            )
        # 独立清理历史版本，不受当前 collection 是否有可见文档影响。
        async for entry in manifest.find({}).sort("checked_at", 1).limit(100):
            current = await coll.find_one({"_id": entry["owner"]})
            if current and "memory_refs" in current:
                from agent.platforms.persistence.mongo.memory_records import hydrate

                current = await hydrate(coll, current, ids=[entry["memory_id"]])
            live = current and any(
                m["status"] == "active"
                and (not m.get("expires_at") or m["expires_at"] > now())
                and doc_id(entry["owner"], m) == entry["_id"]
                for m in current["memories"]
            )
            if live:
                await manifest.update_one(
                    {"_id": entry["_id"]}, {"$set": {"checked_at": time.time()}}
                )
                continue
            response = await http.delete(
                f"/collections/{quote(cfg.rag_collection, safe='')}/documents/{entry['_id']}"
            )
            if response.status_code != 404:
                response.raise_for_status()
                if response.json().get("code") != "OK":
                    raise ValueError("memory_index_delete_failed")
            await manifest.update_one(
                {"_id": entry["_id"]},
                {"$set": {"status": "removed", "checked_at": time.time()}},
            )
