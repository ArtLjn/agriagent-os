"""长期记忆检索、个性化投影与 observation 端口。"""

from __future__ import annotations

from typing import Any

from agent.domains.harness.memory.models import MemorySearchResult

_DIAGNOSTIC_TEXT_CHARS = 160
_DIAGNOSTIC_CONTEXT_CHARS = 4000


async def search(
    *,
    user_id: str,
    farm_id: int,
    query: str = "",
    scope: str = "farm",
    dependencies: list[str] | None = None,
) -> MemorySearchResult:
    """兼容旧调用方的全局个人记忆检索端口。"""
    from agent.domains.harness.memory.personalization import visible_memories
    from agent.platforms.persistence.mongo import personalization_store

    # 旧入口没有可信 farm_uid，只允许全局个人记录，不能把旧数字 ID 视作授权。
    document = await personalization_store.load(user_id)
    if not document["settings"]["use_saved_memories"]:
        return []
    return [
        record
        for record in visible_memories(document, "")
        if record["scope"] == "user" and record["status"] == "active"
    ]


async def observe(
    *,
    user_id: str,
    farm_id: int,
    conversation_id: str,
    turn_id: str,
    user_input: str,
    assistant_answer: str,
    metadata: dict[str, Any] | None = None,
    conversation_revision: int = 0,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """幂等保存受控 observation 事件，但不把它升级为长期事实。"""
    from agent.config import settings

    if not settings.mongodb.enabled:
        return {
            "accepted": False,
            "persisted": False,
            "status": "unavailable",
            "source_status": "unavailable",
            "code": "memory_observation_unavailable",
        }

    from agent.platforms.persistence.mongo import chat_store

    observation_id = idempotency_key or f"turn:{turn_id}:memory-observation"
    result = await chat_store.append_observation(
        observation_id=observation_id,
        user_id=user_id,
        farm_id=farm_id,
        conversation_id=conversation_id,
        payload={
            "turnId": turn_id,
            "conversationRevision": conversation_revision,
            "scope": "conversation",
            "status": "pending",
            "sourceStatus": "mongo",
            "userInputSummary": user_input[:500],
            "assistantResponseSummary": assistant_answer[:500],
            "metadata": metadata or {},
        },
    )
    return {
        "accepted": False,
        "persisted": result.get("status") in {"ready", "idempotent"},
        "status": result.get("status", "unavailable"),
        "source_status": result.get("source_status", "unavailable"),
        "observation_id": observation_id,
        "code": result.get("code"),
    }


__all__ = ["load_context_candidates", "observe", "search"]


async def load_context_candidates(
    user_id: str, farm_uid: str, query: str, control: dict | None = None
) -> dict:
    """有界检索与远程语义补充同受存储超时约束，随后校验发布版本。"""
    import asyncio

    from agent.config import memory_runtime
    from agent.domains.harness.memory.personalization import rank_context_records
    from agent.platforms.persistence.memory_index import retrieve
    from agent.platforms.persistence.mongo import personalization_store as store

    async with asyncio.timeout(memory_runtime.context_timeout):
        control = control or await store.load(user_id, memory_ids=[])
        if not control["settings"]["use_saved_memories"]:
            return control
        diagnostics = {}
        # 词项和语义是互补候选，远程超时仍保留词项结果，不阻塞正常对话。
        doc, ids = await asyncio.gather(
            store.load(user_id, query=query, farm_uid=farm_uid, diversify=True),
            retrieve(control, farm_uid, query, diagnostics=diagnostics),
        )
        lexical_ids = [m["memory_id"] for m in doc["memories"]]
        if ids:
            extra = await store.load(user_id, memory_ids=ids)
            if extra["revision"] != doc["revision"]:
                doc = await store.load(user_id, query=query, farm_uid=farm_uid)
                lexical_ids = [m["memory_id"] for m in doc["memories"]]
                ids = []
                diagnostics.update(status="version_changed", hit_count=0)
            else:
                known = {m["memory_id"] for m in doc["memories"]}
                doc["memories"].extend(
                    m for m in extra["memories"] if m["memory_id"] not in known
                )
        union_count = len(doc["memories"])
        doc["memories"] = rank_context_records(doc["memories"], lexical_ids, ids)
        diagnostics.update(
            query=query,
            collection=memory_runtime.rag_collection,
            configured=bool(memory_runtime.rag_url and memory_runtime.rag_api_key),
            lexical_count=len(lexical_ids),
            union_count=union_count,
            fused_count=len(doc["memories"]),
            fusion_dropped_count=union_count - len(doc["memories"]),
            cards=[
                {
                    "memory_id": record["memory_id"],
                    "revision": record["revision"],
                    "text": record["text"][:_DIAGNOSTIC_TEXT_CHARS],
                    "truncated": len(record["text"]) > _DIAGNOSTIC_TEXT_CHARS,
                    "lexical_rank": lexical_ids.index(record["memory_id"]) + 1
                    if record["memory_id"] in lexical_ids
                    else None,
                    "semantic_rank": ids.index(record["memory_id"]) + 1
                    if record["memory_id"] in ids
                    else None,
                }
                for record in doc["memories"]
            ],
        )
        doc["_retrieval"] = diagnostics
        return doc


async def _compile_context(
    doc: dict, user_id: str, farm_uid: str, query: str, history: list
) -> dict:
    """最多两次语义阅读与一轮补查；只把服务端原文引用交给回答模型。"""
    import asyncio
    from itertools import zip_longest

    from agent.config import memory_runtime
    from agent.domains.harness.memory.inference import read_context
    from agent.domains.harness.memory.personalization import (
        MemoryError,
        context_candidates,
    )
    from agent.platforms.persistence.mongo import personalization_store as store

    facts = context_candidates(doc, farm_uid, query)
    recent = [
        {
            "role": m["role"],
            "content": str(m.get("content", ""))[
                : memory_runtime.context_history_chars
            ],
        }
        for m in history[-2:]
        if m.get("role") in {"user", "assistant"}
    ]
    selected, searches = [], []
    for attempt in range(2):
        # 内部 ID/版本不占模型注意力，模型只能引用当前候选列表的索引。
        inputs = [
            {
                "ref": i,
                **{k: v for k, v in f.items() if k not in {"memory_id", "revision"}},
            }
            for i, f in enumerate(facts)
        ]
        reading = await read_context(query, inputs, recent, can_search=attempt == 0)
        selected, recommended_aspects = [], set()
        for item in reading.selections:
            fact = facts[item.ref]
            use = "clarify" if fact.get("state") == "conflicted" else item.use
            if use == "recommend" and item.aspect in recommended_aspects:
                continue
            if use == "recommend":
                recommended_aspects.add(item.aspect)
            selected.append(
                {
                    "fact": fact,
                    "use": use,
                    "applicability": item.applicability,
                }
            )
        if attempt or not reading.search_queries:
            break
        searches = list(dict.fromkeys(reading.search_queries))
        async with asyncio.timeout(memory_runtime.context_timeout):
            extra = await asyncio.gather(
                *(
                    store.load(user_id, query=q, farm_uid=farm_uid, diversify=True)
                    for q in searches
                )
            )
        if any(d["revision"] != doc["revision"] for d in extra):
            raise MemoryError("memory_version_conflict", "整理依据期间记忆已变化")
        # 补查按来源轮转，防止一个高频主题挤掉其他用途的事实。
        merged, seen = [], set()
        for row in zip_longest(*(d["memories"] for d in extra), doc["memories"]):
            for record in row:
                if record and record["memory_id"] not in seen:
                    merged.append(record)
                    seen.add(record["memory_id"])
        doc = {**doc, "memories": merged}
        facts = context_candidates(doc, farm_uid, query)
    return {
        "selected": selected,
        "candidate_count": len(facts),
        "searches": searches,
        "status": "ready" if selected else "no_relevant_evidence",
    }


async def get_personalization_context(
    *,
    user_id: str,
    farm_uid: str,
    query: str = "",
    temporary: bool = False,
    previous: dict | None = None,
    history: list | None = None,
) -> dict:
    """每步校验权威版本，只在本轮首次或版本改变时整理回答依据。"""
    import asyncio
    import logging
    import time

    from openai import APIError

    from agent.config import memory_runtime
    from agent.domains.harness.memory.personalization import MemoryError
    from agent.platforms.persistence.mongo import personalization_store as store

    if temporary:
        return {}
    started = time.monotonic()
    # 短追问仍携带最近的用户话题；助手建议不能当作用户偏好或扩大检索主题。
    recent_user_text = " ".join(
        str(message.get("content", ""))
        for message in (history or [])[-4:]
        if message.get("role") == "user" and message.get("content") != query
    )[-memory_runtime.retrieval_history_chars :]
    retrieval_query = query[: memory_runtime.retrieval_query_chars]
    if recent_user_text:
        retrieval_query += "\n最近用户话题：" + recent_user_text
    key = [user_id, farm_uid, query]
    cached = (previous or {}).get("_personalization_cache", {})
    try:
        async with asyncio.timeout(memory_runtime.context_timeout):
            control = await store.load(user_id, memory_ids=[])
        hit = cached.get("key") == key and cached.get("revision") == control["revision"]
        hit = hit and cached.get("retrieval_query") == retrieval_query
        hit = hit and cached.get("mode") == memory_runtime.context_mode
        if not control["settings"]["use_saved_memories"]:
            plan = {"selected": [], "candidate_count": 0, "status": "disabled"}
        elif hit:
            plan = cached["plan"]
        elif not query or control["revision"] == 0:
            plan = {
                "selected": [],
                "candidate_count": 0,
                "status": "no_relevant_evidence",
            }
        else:
            plan = {"selected": [], "candidate_count": 0, "status": "unavailable"}
            try:
                async with asyncio.timeout(memory_runtime.context_compile_timeout):
                    doc = await load_context_candidates(
                        user_id, farm_uid, retrieval_query, control
                    )
                    control = doc
                    if memory_runtime.context_mode == "read":
                        plan = await _compile_context(
                            doc, user_id, farm_uid, query, history or []
                        )
                    else:
                        from agent.domains.harness.memory.personalization import (
                            proactive_context,
                        )

                        plan = proactive_context(doc, farm_uid, query)
                    plan["retrieval"] = doc.get("_retrieval", {})
            except (
                APIError,
                ValueError,
                MemoryError,
                RuntimeError,
                TimeoutError,
            ) as exc:
                plan["code"] = getattr(exc, "code", type(exc).__name__)
                logging.getLogger(__name__).warning(
                    "memory context compilation unavailable code=%s",
                    getattr(exc, "code", "memory_context_compile_failed"),
                )
        # 查询和模式属于本轮缓存签名，不能跨话题或部署模式复用旧候选。
        plan.setdefault("retrieval", {}).update(
            query=retrieval_query,
            configured=bool(memory_runtime.rag_url and memory_runtime.rag_api_key),
            collection=memory_runtime.rag_collection,
        )
        result = await _publish_context(key, control, plan, hit, started)
        result["_personalization_cache"].update(
            retrieval_query=retrieval_query, mode=memory_runtime.context_mode
        )
        return result
    except (MemoryError, RuntimeError, TimeoutError) as exc:
        logging.getLogger(__name__).warning(
            "personalization unavailable code=%s",
            getattr(exc, "code", "memory_runtime_unavailable"),
        )
        return {
            "personalization_diagnostics": {
                "status": "unavailable",
                "code": getattr(exc, "code", type(exc).__name__),
                "mode": memory_runtime.context_mode,
            }
        }


async def _publish_context(
    key: list, control: dict, plan: dict, hit: bool, started: float
) -> dict:
    """版本和有效期复查后准备记忆块；最终请求还需核对二次预算裁剪。"""
    import asyncio
    import time

    from agent.config import memory_runtime, settings
    from agent.domains.harness.memory.personalization import (
        answer_context,
        apply_business_profile,
        context_candidates,
    )
    from agent.domains.harness.observability.trace import record as trace_record
    from agent.platforms.persistence.mongo import personalization_store as store

    user_id, farm_uid, query = key
    # 模型整理可能较慢，发布前精确读取选中记录；删除、过期、关闭读取都不能由缓存复活。
    async with asyncio.timeout(memory_runtime.context_timeout):
        live = await store.load(
            user_id,
            memory_ids=list({s["fact"]["memory_id"] for s in plan["selected"]}),
        )
    manifest = settings.plugins.manifest
    live = apply_business_profile(
        live,
        manifest.name if manifest else None,
        manifest.assistant_name if manifest else "",
    )
    selected_count = len(plan["selected"])
    if live["revision"] != control["revision"]:
        plan = {
            **plan,
            "selected": [],
            "status": "changed_during_read",
        }
    current = context_candidates(live, farm_uid, query)
    valid = [s for s in plan["selected"] if s["fact"] in current]
    text, injected = answer_context(live, valid, plan["status"])
    diagnostics = {
        "stage": "prepared",
        "status": plan["status"],
        "reading_enabled": live["settings"]["use_saved_memories"],
        "cached": hit,
        "candidate_count": plan["candidate_count"],
        "selected_count": len(valid),
        "injected_count": len(injected),
        "validation_dropped_count": selected_count - len(valid),
        "budget_dropped_count": len(valid) - len(injected),
        "code": plan.get("code"),
        "revision": live["revision"],
        "sources": [
            {
                "memory_id": s["fact"]["memory_id"],
                "slot": s["fact"].get("slot"),
                "use": s["use"],
            }
            for s in injected
        ],
        "searches": plan.get("searches", []),
        "chars": len(text),
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "mode": memory_runtime.context_mode,
        "retrieval": plan.get("retrieval", {}),
    }
    trace_record(
        node_type="memory",
        node_name="answer_memory_context",
        phase="reasoning",
        output_data=diagnostics,
    )
    return {
        "personalization": text,
        "personalization_revision": live["revision"],
        "personalization_diagnostics": diagnostics,
        "_personalization_cache": {
            "key": key,
            "revision": control["revision"],
            "plan": plan,
        },
    }


def injection_diagnostics(
    snapshot: dict, messages: list[dict], *, before_budget: list[dict] | None = None
) -> dict:
    """以预算裁剪后的真实请求核对记忆块；准备成功不能冒充已发送。"""
    diagnostics = dict(snapshot.get("personalization_diagnostics") or {})
    expected = snapshot.get("personalization", "")
    actual = "\n".join(
        message["content"]
        for message in messages
        if message.get("role") == "user"
        and isinstance(message.get("content"), str)
        and message["content"].startswith("<user-personalization>")
    )
    prepared_count = diagnostics.get("injected_count")
    if actual and actual == expected:
        status = "included"
    elif actual:
        status = "modified"
    elif expected:
        status = (
            "budget_omitted"
            if any(m.get("content") == expected for m in before_budget or [])
            else "not_in_request"
        )
    else:
        status = "not_prepared"
    return {
        **diagnostics,
        "stage": "complete",
        "status": diagnostics.get("status", "not_recorded"),
        "prepared_count": prepared_count,
        # 内容被二次裁剪时不猜测剩余事实数；完整请求文本预览仍可核查。
        "injected_count": prepared_count
        if status == "included"
        else None
        if status == "modified"
        else 0,
        "sources": diagnostics.get("sources", []) if status == "included" else [],
        "injection": {
            "status": status,
            "chars": len(actual),
            "text": actual[:_DIAGNOSTIC_CONTEXT_CHARS],
            "truncated": len(actual) > _DIAGNOSTIC_CONTEXT_CHARS,
        },
    }
