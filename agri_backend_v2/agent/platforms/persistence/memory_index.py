"""QuillRAG 记忆索引适配；Mongo 主数据验证是唯一可见性依据。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from itertools import zip_longest
from urllib.parse import quote, urlparse

import httpx
from pymongo import ReturnDocument

from agent.config import DEFAULT_MEMORY_RAG_COLLECTION
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
        # 本机适配服务不能被桌面全局 HTTP 代理转发到外部。
        trust_env=urlparse(cfg.rag_url).hostname
        not in {"localhost", "127.0.0.1", "::1"},
    )


async def retrieve(
    document: dict, farm_uid: str, query: str, *, diagnostics: dict | None = None
) -> list[str]:
    """全局与农场范围分别过滤，返回 ID 后仍必须回查权威版本。"""
    stats = diagnostics if diagnostics is not None else {}
    stats.update(status="not_configured", hit_count=0)
    if not cfg.rag_url or not cfg.rag_api_key or not query:
        return []
    started = time.monotonic()
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
                            "top_k": cfg.retrieval_limit,
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
            for response in results:
                response.raise_for_status()
                if response.json().get("code") != "OK":
                    raise ValueError("memory_retrieve_failed")
            modes = {
                response.json().get("data", {}).get("actual_mode", "hybrid")
                for response in results
            }
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
            # 按范围轮转而非全局结果在前，防止当前农场事实在融合前就落到队尾。
            scoped_hits = [
                response.json().get("data", {}).get("results", [])
                for response in results
            ]
            ids = [
                valid[hit["doc_id"]]
                for row in zip_longest(*scoped_hits)
                for hit in row
                if hit and hit.get("doc_id") in valid
            ]
            ids = list(dict.fromkeys(ids))
            stats.update(
                status="ready" if "bm25" not in modes else "lexical_fallback",
                hit_count=len(ids),
                actual_modes=sorted(modes),
            )
            return ids
    except (TimeoutError, httpx.HTTPError, ValueError) as exc:
        stats.update(
            status="timeout" if isinstance(exc, TimeoutError) else "unavailable"
        )
        logger.warning(
            "memory semantic retrieval fallback code=memory_retrieve_unavailable"
        )
        return []
    finally:
        stats["elapsed_ms"] = round((time.monotonic() - started) * 1000)


async def _index_record(http, manifest, owner: str, record: dict, semaphore) -> None:
    """一个版本一条索引，网络失败可重放；并发受限且提交后仍由主数据控制可见性。"""
    identifier = doc_id(owner, record)
    manifest_id = f"{cfg.rag_collection}:{identifier}"
    async with semaphore:
        await manifest.update_one(
            {"_id": manifest_id},
            {
                "$setOnInsert": {
                    "collection": cfg.rag_collection,
                    "doc_id": identifier,
                    "owner": owner,
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
                        "owner": owner,
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
        await manifest.update_one({"_id": manifest_id}, {"$set": {"status": "ready"}})


async def sync_one(*, owner: str | None = None) -> None:
    """先登记版本文档再上传；崩溃遗留的版本可通过清单重试或删除。"""
    if not cfg.rag_url or not cfg.rag_api_key:
        return
    coll = store.collection()
    manifest = coll.database[MANIFEST_COLLECTION]
    document = await coll.find_one_and_update(
        {
            **({"_id": owner} if owner else {}),
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
            indexed = []
            finished = True
            ready = {
                row["doc_id"]
                async for row in manifest.find(
                    {
                        "owner": document["_id"],
                        "status": "ready",
                        "collection": cfg.rag_collection,
                    }
                )
            }
            for record in document["memories"]:
                if record["status"] != "active" or (
                    record.get("expires_at") and record["expires_at"] <= now()
                ):
                    continue
                identifier = doc_id(document["_id"], record)
                if identifier in ready:
                    continue
                if len(indexed) >= cfg.index_batch_size:
                    finished = False
                    break
                indexed.append(record)
            semaphore = asyncio.Semaphore(cfg.index_concurrency)
            results = await asyncio.gather(
                *(
                    _index_record(http, manifest, document["_id"], r, semaphore)
                    for r in indexed
                ),
                return_exceptions=True,
            )
            failures = [result for result in results if isinstance(result, Exception)]
            await coll.update_one(
                {"_id": document["_id"], "revision": document["revision"]},
                {
                    "$set": {
                        "index_pending": not finished or bool(failures),
                        "index_available_at": time.time()
                        + (cfg.poll_seconds if failures else 0),
                        **(
                            {"indexed_revision": document["revision"]}
                            if finished and not failures
                            else {}
                        ),
                    }
                },
            )
            if failures:
                logger.warning(
                    "memory index partial failure code=memory_index_batch_failed count=%s",
                    len(failures),
                )
        await _cleanup_obsolete(http, coll, manifest, owner)


async def _cleanup_obsolete(http, coll, manifest, owner: str | None) -> None:
    """按用户批量回查权威版本，避免清理 100 条索引就读取 100 次完整画像。"""
    from agent.platforms.persistence.mongo.memory_records import hydrate

    # 旧清单仅属于旧默认集合；不能向新模型集合发送旧集合的清理请求。
    collection_filter = {"collection": cfg.rag_collection}
    if cfg.rag_collection == DEFAULT_MEMORY_RAG_COLLECTION:
        collection_filter = {
            "$or": [collection_filter, {"collection": {"$exists": False}}]
        }
    entries = [
        entry
        async for entry in manifest.find(
            {
                "status": {"$ne": "removed"},
                **collection_filter,
                **({"owner": owner} if owner else {}),
            }
        )
        .sort("checked_at", 1)
        .limit(cfg.index_cleanup_batch_size)
    ]
    grouped: dict[str, list[dict]] = {}
    for entry in entries:
        grouped.setdefault(entry["owner"], []).append(entry)
    for entry_owner, records in grouped.items():
        current = await coll.find_one({"_id": entry_owner})
        if current and "memory_refs" in current:
            current = await hydrate(
                coll, current, ids=[r["memory_id"] for r in records]
            )
        live_ids = {
            doc_id(entry_owner, m)
            for m in (current or {}).get("memories", [])
            if m["status"] == "active"
            and (not m.get("expires_at") or m["expires_at"] > now())
        }
        for entry in records:
            identifier = entry.get("doc_id", entry["_id"])
            if identifier in live_ids:
                await manifest.update_one(
                    {"_id": entry["_id"]}, {"$set": {"checked_at": time.time()}}
                )
                continue
            response = await http.delete(
                f"/collections/{quote(cfg.rag_collection, safe='')}/documents/{identifier}"
            )
            if response.status_code != 404:
                response.raise_for_status()
                if response.json().get("code") != "OK":
                    raise ValueError("memory_index_delete_failed")
            await manifest.update_one(
                {"_id": entry["_id"]},
                {"$set": {"status": "removed", "checked_at": time.time()}},
            )
