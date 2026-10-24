"""记忆语义边界：有界抽取、完整性复核和候选归并，禁止直接持久化。"""

from __future__ import annotations

import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from agent.config import memory_runtime
from agent.domains.harness.memory.facts import (
    MAX_FACTS_PER_MEMORY,
    AtomicFact,
    initialize_atoms,
    query_terms,
)
from agent.domains.harness.memory.personalization import MemoryCategory, MemoryError
from agent.platforms.llm.structured import structured_completion
from agent.prompts import render_prompt

MODEL_TIMEOUT_SECONDS = 30
EXTRACTION_TOKENS = 1500
ALIGNMENT_TOKENS = 2000
DECOMPOSITION_TOKENS = 2000
VERIFICATION_TOKENS = 100
CONTEXT_SELECTION_TOKENS = 700
# 表达偏好使用受控值，避免模型每次换一种说法导致证据永远无法累计。
PRESENTATION_VALUES = {
    "response.detail_level": {
        "concise": "偏好简洁回答",
        "balanced": "偏好适中长度的回答",
        "detailed": "偏好详细回答",
    },
    "response.format": {"table": "偏好表格呈现", "list": "偏好分点列举"},
    "response.style": {
        "friendly": "偏好亲和友善的语气",
        "professional": "偏好专业严谨的语气",
        "efficient": "偏好直接给结论和行动项",
    },
}


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=1, max_length=500)
    category: MemoryCategory = "general"
    kind: Literal["preference", "habit", "episode"] = "preference"
    value: str | None = None
    slot: str = Field(default="", max_length=100)
    scope: Literal["user", "user_farm"] = "user_farm"
    target_memory_id: str | None = None
    target_slot: str | None = None
    relation: Literal["new", "reinforce", "merge", "contradict", "conflict"] = "new"
    temporal_scope: Literal["current", "historical"] = "current"
    time_evidence: str = Field(default="", max_length=100)
    conditions: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        default_factory=list, max_length=10
    )
    merged_text: str | None = Field(default=None, min_length=1, max_length=500)
    durability: Literal["stable", "temporary", "uncertain", "sensitive"] = "stable"
    reason: str = Field(default="", max_length=300)


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[Candidate] = Field(max_length=MAX_FACTS_PER_MEMORY)


class ExtractionCheck(BaseModel):
    """独立复核不能用缺省通过掩盖少抽、混合事实或条件丢失。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    complete: bool
    atomic: bool
    grounded: bool
    conditions_preserved: bool


class Alignment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    candidate_index: int = Field(ge=0, lt=MAX_FACTS_PER_MEMORY)
    target_memory_id: str | None = None
    target_slot: str | None = None
    relation: Literal["new", "reinforce", "merge", "contradict", "conflict"]
    conditions_equivalent: bool = False
    merged_text: str | None = Field(default=None, min_length=1, max_length=500)


class Alignments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alignments: list[Alignment] = Field(max_length=MAX_FACTS_PER_MEMORY)


class Decomposition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: list[AtomicFact] = Field(min_length=1, max_length=MAX_FACTS_PER_MEMORY)


class DecompositionCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    equivalent: bool


class ContextSelection(BaseModel):
    """模型只选择服务端事实，不允许改写记忆或生成新的用户属性。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    ref: int = Field(ge=0, lt=memory_runtime.context_fact_limit)
    use: Literal["answer", "recommend", "avoid", "style", "clarify"]
    applicability: Literal["direct", "conditional"]
    aspect: str = Field(min_length=1, max_length=30)


class ContextReading(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    selections: list[ContextSelection] = Field(
        max_length=memory_runtime.context_selection_limit
    )
    search_queries: list[Annotated[str, Field(min_length=1, max_length=30)]] = Field(
        default_factory=list, max_length=memory_runtime.context_search_limit
    )


async def read_context(
    query: str, facts: list[dict], history: list[dict], *, can_search: bool
) -> ContextReading:
    """按当前任务先提取可用依据，再让主模型作答；输出没有自由生成的事实。"""
    from datetime import datetime

    result = await structured_completion(
        ContextReading,
        temperature=0,
        max_tokens=CONTEXT_SELECTION_TOKENS,
        timeout=memory_runtime.context_compile_timeout,
        messages=[
            {
                "role": "system",
                "content": render_prompt("memory_read_context"),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "query": query,
                        "history": history,
                        "facts": facts,
                        "can_search": can_search,
                        "current_time": datetime.now().strftime("%Y-%m-%d %H:%M %A"),
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    refs = [item.ref for item in result.selections]
    if len(set(refs)) != len(refs) or any(ref >= len(facts) for ref in refs):
        raise MemoryError("memory_context_invalid_reference", "记忆依据引用无效")
    return result


async def normalize_record(record: dict) -> None:
    """旧主题仅在涉及更新时拆分，独立核对无增删后随本次 CAS 一起提交。"""

    if "atoms" in record:
        return
    result = await structured_completion(
        Decomposition,
        temperature=0,
        max_tokens=DECOMPOSITION_TOKENS,
        timeout=MODEL_TIMEOUT_SECONDS,
        messages=[
            {
                "role": "system",
                "content": render_prompt("memory_normalize_record"),
            },
            {"role": "user", "content": record["text"]},
        ],
    )
    facts = result.facts
    if len({fact.slot for fact in facts}) != len(facts) or any(
        fact.evidence not in record["text"] for fact in facts
    ):
        raise MemoryError("memory_decomposition_invalid", "旧记忆拆分证据不完整")
    checked = await structured_completion(
        DecompositionCheck,
        temperature=0,
        max_tokens=VERIFICATION_TOKENS,
        timeout=MODEL_TIMEOUT_SECONDS,
        messages=[
            {
                "role": "system",
                "content": render_prompt("memory_verify_decomposition"),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "original": record["text"],
                        "facts": [f.model_dump() for f in facts],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    if not checked.equivalent:
        raise MemoryError(
            "memory_decomposition_incomplete", "旧记忆拆分未通过完整性核验"
        )
    record["atoms"] = initialize_atoms(record, facts)


async def align_candidates(
    candidates: list[Candidate], existing: list[dict]
) -> list[Candidate]:
    """只对已通过稳定性筛选的观察做语义归并，禁止旧记忆反向制造本轮证据。"""

    if len(candidates) > 1 and len(existing) > memory_runtime.review_memory_limit:
        aligned = []
        for candidate in candidates:
            aligned.extend(await align_candidates([candidate], existing))
        return aligned

    # 优先同主题，再做跨分类比较；旧记忆不能仅因最近未更新而丢失去重机会。
    categories = {c.category for c in candidates}
    keys = {c.key for c in candidates}
    terms = query_terms(" ".join(c.text for c in candidates))
    import heapq

    slots = {c.slot for c in candidates if c.slot}
    existing = heapq.nlargest(
        memory_runtime.review_memory_limit,
        existing,
        key=lambda m: (
            bool(slots & {a["slot"] for a in m.get("atoms", [])}),
            m.get("key") in keys,
            len(terms & query_terms(m["text"])),
            m.get("category") in categories,
        ),
    )
    # 单条候选独享预算；长证据不进入归并提示，目标正文与事实身份必须保留。
    limited, used_bytes = [], 0
    for record in existing:
        projected = {
            k: record.get(k) for k in ("memory_id", "key", "scope", "category", "text")
        }
        if "atoms" in record:
            projected["atoms"] = [
                {
                    k: a[k]
                    for k in (
                        "slot",
                        "text",
                        "conditions",
                        "temporal_scope",
                        "state",
                        "alternatives",
                    )
                    if k in a
                }
                for a in record["atoms"]
            ]
        size = len(json.dumps(projected, ensure_ascii=False).encode())
        if used_bytes + size > memory_runtime.review_bytes:
            break
        limited.append(record)
        used_bytes += size
    if existing and not limited:
        raise MemoryError("memory_alignment_budget_exceeded", "归并证据超过独立预算")
    existing = limited
    result = await structured_completion(
        Alignments,
        temperature=0,
        max_tokens=ALIGNMENT_TOKENS,
        timeout=MODEL_TIMEOUT_SECONDS,
        messages=[
            {
                "role": "system",
                "content": render_prompt("memory_align_candidates"),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "candidates": [
                            {**c.model_dump(), "candidate_index": index}
                            for index, c in enumerate(candidates)
                        ],
                        "existing_memories": [
                            {
                                **{
                                    k: m.get(k)
                                    for k in (
                                        "memory_id",
                                        "key",
                                        "scope",
                                        "category",
                                        "text",
                                    )
                                },
                                **(
                                    {
                                        "atoms": [
                                            {
                                                k: a[k]
                                                for k in (
                                                    "slot",
                                                    "text",
                                                    "conditions",
                                                    "temporal_scope",
                                                    "state",
                                                    "alternatives",
                                                )
                                                if k in a
                                            }
                                            for a in m["atoms"]
                                        ]
                                    }
                                    if "atoms" in m
                                    else {}
                                ),
                            }
                            for m in existing
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    indexes = [item.candidate_index for item in result.alignments]
    if sorted(indexes) != list(range(len(candidates))):
        raise MemoryError("memory_alignment_incomplete", "归并结果没有完整覆盖本轮事实")
    targets = {m["memory_id"]: m for m in existing}
    for item in result.alignments:
        target = targets.get(item.target_memory_id)
        candidate = candidates[item.candidate_index]
        if (
            item.relation == "merge"
            and target
            and candidate.scope != target.get("scope", candidate.scope)
        ):
            # 同主题不代表同一作用范围。新增事实独立保存，既不缩小个人偏好的
            # 可见范围，也不把农场限定事实提升为全局事实；旧目标保持原样。
            item.relation = "new"
            item.target_memory_id = None
            item.target_slot = None
            item.conditions_equivalent = False
    legacy_targets = {
        item.target_memory_id
        for item in result.alignments
        if item.relation != "new"
        and item.target_memory_id in targets
        and "atoms" not in targets[item.target_memory_id]
    }
    if legacy_targets:
        for identifier in legacy_targets:
            await normalize_record(targets[identifier])
        return await align_candidates(candidates, existing)
    aligned = []
    for item in result.alignments:
        if item.relation != "new" and item.target_memory_id not in targets:
            raise MemoryError(
                "memory_alignment_unknown_target", "归并目标不在有效候选中"
            )
        target = targets.get(item.target_memory_id)
        candidate = candidates[item.candidate_index]
        if target and candidate.scope != target.get("scope", candidate.scope):
            if candidate.scope == "user" and item.relation in {
                "contradict",
                "reinforce",
                "conflict",
            }:
                candidate = candidate.model_copy(update={"scope": target["scope"]})
            else:
                raise MemoryError(
                    "memory_alignment_scope_mismatch", "归并不能跨越事实作用范围"
                )
        if item.relation in {"reinforce", "contradict", "conflict"}:
            slots = {atom["slot"] for atom in (target or {}).get("atoms", [])}
            if item.target_slot not in slots:
                raise MemoryError(
                    "memory_alignment_unknown_fact", "归并引用了不存在的原子事实"
                )
        elif item.relation == "merge" and candidate.temporal_scope != "historical":
            # merge 只追加候选自己的事实，不使用模型多填的旧对象槽位。
            # 候选槽位若已存在，事实层仍拒绝覆盖；历史补充继续保留时间分支锚点。
            item.target_slot = None
            item.conditions_equivalent = False
        elif item.target_slot:
            # 历史补充可指向当前对象作锚点，事实层按时间另开槽位；普通 merge 仍禁止覆盖。
            if not (
                item.relation == "merge"
                and candidate.temporal_scope == "historical"
                and item.target_slot
                in {a["slot"] for a in (target or {}).get("atoms", [])}
            ):
                raise MemoryError(
                    "memory_alignment_unexpected_fact", "新增事实不能覆盖已有槽位"
                )
        if item.merged_text:
            raise MemoryError(
                "memory_alignment_whole_text_forbidden", "归并禁止重写整张记忆正文"
            )
        if item.conditions_equivalent and item.target_slot:
            atom = next(a for a in target["atoms"] if a["slot"] == item.target_slot)
            # 条件是自然语言，不能用字符串不等判定新场景；归并器明确确认等价后复用既有表示。
            # 有无条件不能互相消除，历史时间仍由事实层独立分支。
            if candidate.conditions and atom.get("conditions"):
                candidate = candidate.model_copy(
                    update={"conditions": atom["conditions"]}
                )
        candidate = candidate.model_copy(
            update={
                "relation": item.relation,
                "merged_text": None,
                "target_slot": item.target_slot,
                "target_memory_id": item.target_memory_id
                if item.relation != "new"
                else None,
            }
        )
        aligned.append(candidate)
    return aligned


async def extract(text: str, existing: list[dict] | None = None) -> list[Candidate]:
    """观察每轮完整输入，与已有记忆做语义对齐；模型不直接写入。"""

    result = await structured_completion(
        Extraction,
        legacy_array_field="candidates",
        temperature=0,
        max_tokens=EXTRACTION_TOKENS,
        timeout=MODEL_TIMEOUT_SECONDS,
        messages=[
            {
                "role": "system",
                "content": (
                    render_prompt(
                        "memory_extract",
                        presentation_values=json.dumps(
                            PRESENTATION_VALUES, ensure_ascii=False
                        ),
                    )
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"user_input": text},
                    ensure_ascii=False,
                ),
            },
            {"role": "system", "content": render_prompt("memory_extract_guard")},
        ],
    )
    # 先核对整批原文来源，不能因另一个字段异常而绕过伪造证据的拒绝。
    if any(
        candidate.evidence not in text
        or (
            candidate.temporal_scope == "historical"
            and (not candidate.time_evidence or candidate.time_evidence not in text)
        )
        for candidate in result.candidates
    ):
        raise MemoryError(
            "memory_extraction_ungrounded", "抽取证据不是用户原文，需重新抽取"
        )
    candidates = []
    for candidate in result.candidates:
        if candidate.durability != "stable":
            continue
        values = PRESENTATION_VALUES.get(candidate.key)
        if values:
            if candidate.value not in values:
                raise MemoryError(
                    "memory_presentation_value_invalid",
                    "表达偏好缺少规范值，需重新抽取",
                )
            candidate.text = values[candidate.value]
            candidate.category = "response"
        # 冲突需要在提交时结合已发布事实与同轮其他候选判断，抽取不能引用未知目标。
        candidate.relation, candidate.target_memory_id = "new", None
        candidate.target_slot = None
        candidate.merged_text = None
        candidates.append(candidate)
    await verify_extraction(text, candidates)
    return (
        await align_candidates(candidates, existing)
        if candidates and existing
        else candidates
    )


async def verify_extraction(text: str, candidates: list[Candidate]) -> None:
    """在归并前独立核对事实粒度和条件，避免错误原子导致后续局部纠正连带丢失。"""

    checked = await structured_completion(
        ExtractionCheck,
        temperature=0,
        max_tokens=VERIFICATION_TOKENS,
        timeout=MODEL_TIMEOUT_SECONDS,
        messages=[
            {
                "role": "system",
                "content": render_prompt("memory_verify_extraction"),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_input": text,
                        "candidates": [c.model_dump() for c in candidates],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    )
    if not all(checked.model_dump().values()):
        raise MemoryError(
            "memory_extraction_incomplete", "事实粒度或条件未通过完整性核验，需重新抽取"
        )
