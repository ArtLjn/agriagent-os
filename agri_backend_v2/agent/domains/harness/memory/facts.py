"""主题记忆内的原子事实：只更新目标事实，来源与时序不随整段文字漂移。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field

from agent.domains.harness.memory.personalization import (
    MAX_MEMORY_TEXT,
    MemoryError,
    now,
)

MAX_FACTS_PER_MEMORY = 30
MAX_EVIDENCE_TURNS = 100
MAX_FACT_HISTORY = 5
MAX_CONFLICT_ALTERNATIVES = 3


class AtomicFact(BaseModel):
    """slot 标识同一对象与属性；text 保留值、否定和适用条件。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    slot: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=MAX_MEMORY_TEXT)
    evidence: str = Field(min_length=1, max_length=MAX_MEMORY_TEXT)


def initialize_atoms(record: dict, facts: list[AtomicFact]) -> list[dict]:
    """旧正文拆分只分配已有来源，不把迁移计为新的用户证据。"""
    return [
        {
            "slot": fact.slot,
            "text": fact.text,
            "source_type": record["source_type"],
            "source_message_ids": record.get("source_message_ids", []),
            "evidence_turns": record.get("evidence_turns", []),
            "evidence_count": record.get("evidence_count", 1),
            "revision": 1,
            "valid_from": record.get("last_observed_at", 0),
            "last_observed_at": record.get("last_observed_at", 0),
            "updated_at": record["updated_at"],
        }
        for fact in facts
    ]


def update_atom(record: dict, candidate, task: dict) -> bool:
    """按语义对齐后的 slot 更新；旧观察、手工设置和重复事件不能覆盖新事实。"""
    atoms = deepcopy(record.get("atoms", []))
    slot = candidate.target_slot or candidate.slot or candidate.key
    atom = next((item for item in atoms if item["slot"] == slot), None)
    temporal_scope = getattr(candidate, "temporal_scope", "current")
    conditions = getattr(candidate, "conditions", [])
    # 历史或不同场景单独存放，不能因消息较晚而覆盖当前事实。
    if temporal_scope == "historical" or (
        atom
        and atom.get("conditions")
        and conditions
        and sorted(conditions) != sorted(atom["conditions"])
    ):
        discriminator = json.dumps(
            [conditions, temporal_scope, getattr(candidate, "time_evidence", "")],
            ensure_ascii=False,
        )
        slot = f"{slot.split('@')[0]}@{hashlib.sha256(discriminator.encode()).hexdigest()[:12]}"
        atom = next((item for item in atoms if item["slot"] == slot), None)
    if candidate.target_slot and atom is None and slot == candidate.target_slot:
        raise MemoryError("memory_fact_not_found", "目标事实已变化，请重新读取")
    observed_at = task.get("observed_at", 0)
    explicit = task.get("source_type") == "explicit"
    repeated_turn = bool(atom and task["turn_id"] in atom.get("evidence_turns", []))
    conflicting = bool(
        atom
        and (
            candidate.relation == "conflict"
            or (
                repeated_turn
                and atom["text"] != candidate.text
                and candidate.relation != "reinforce"
            )
            or (
                observed_at > 0
                and observed_at == atom.get("last_observed_at", 0)
                and candidate.relation == "contradict"
            )
        )
    )
    if atom:
        # 后台可能先于显式工具落库；本轮显式保存可提升来源，但不能重复累计证据。
        if (
            repeated_turn
            and not conflicting
            and (not explicit or atom["source_type"] == "explicit")
        ):
            return False
        if observed_at < atom.get("last_observed_at", 0):
            return False
        if atom["source_type"] == "explicit" and not explicit:
            from datetime import datetime

            if (
                candidate.relation != "contradict"
                or observed_at <= datetime.fromisoformat(atom["updated_at"]).timestamp()
            ):
                return False
        if candidate.relation == "merge" and not conflicting:
            raise MemoryError("memory_fact_conflict", "不同事实不能覆盖同一事实槽位")
    else:
        if len(atoms) >= MAX_FACTS_PER_MEMORY:
            raise MemoryError("memory_fact_limit", "主题内事实已达上限")
        atom = {"slot": slot, "revision": 0, "evidence_turns": []}
        atoms.append(atom)
    previous = {
        k: deepcopy(atom[k])
        for k in (
            "text",
            "valid_from",
            "last_observed_at",
            "source_type",
            "source_message_ids",
            "state",
            "alternatives",
        )
        if k in atom
    }
    if conflicting:
        alternatives = atom.get(
            "alternatives",
            [
                {
                    "text": atom["text"],
                    "source_message_ids": atom.get("source_message_ids", []),
                }
            ],
        )
        if candidate.text not in {a["text"] for a in alternatives}:
            alternatives.append(
                {
                    "text": candidate.text,
                    "source_message_ids": [f"turn:{task['turn_id']}"],
                }
            )
        atom["alternatives"] = alternatives[-MAX_CONFLICT_ALTERNATIVES:]
        atom["state"] = "conflicted"
    elif candidate.relation == "contradict" and atom["revision"]:
        previous["valid_to"] = observed_at
        atom["history"] = [*atom.get("history", []), previous][-MAX_FACT_HISTORY:]
        atom.pop("alternatives", None)
        atom["state"] = "active"
    elif atom.get("state") != "conflicted":
        atom["state"] = "active"
    changed_value = candidate.relation == "contradict" or atom["revision"] == 0
    # 旧值仅保留有界历史供时间查询；当前证据不能继承旧值的支持次数。
    turns = [] if changed_value else atom.get("evidence_turns", [])
    turns = list(dict.fromkeys([*turns, task["turn_id"]]))[-MAX_EVIDENCE_TURNS:]
    atom.update(
        text="该事实存在未解决的矛盾，需要结合用户澄清"
        if atom.get("state") == "conflicted"
        else (
            atom.get("text", candidate.text)
            if candidate.relation == "reinforce"
            else candidate.text
        ),
        temporal_scope=temporal_scope,
        time_evidence=getattr(candidate, "time_evidence", ""),
        conditions=conditions or atom.get("conditions", []),
        source_type="explicit" if explicit else "inferred",
        source_message_ids=[f"turn:{value}" for value in turns],
        evidence_turns=turns,
        evidence_count=len(turns),
        revision=atom["revision"] + 1,
        valid_from=observed_at
        if changed_value
        else atom.get("valid_from", observed_at),
        last_observed_at=observed_at,
        updated_at=now(),
    )
    text = "；".join(item["text"] for item in atoms)
    if len(text) > MAX_MEMORY_TEXT:
        raise MemoryError("memory_text_limit", "主题内容过长，需拆成独立主题")
    record.update(atoms=atoms, text=text)
    return True


def erase_memory(record: dict) -> None:
    """遗忘必须清掉事实及其来源，不能只清空用于展示的聚合正文。"""
    record.update(
        status="deleted", text="", conditions=[], key="", source_message_ids=[]
    )
    for field in (
        "atoms",
        "evidence_turns",
        "evidence_conversations",
        "conflict_turns",
        "review_reason",
        "conflict_reason",
        "confidence",
    ):
        record.pop(field, None)


def query_terms(text: str) -> set[str]:
    """中文使用重叠双字，避免固定切片把‘吃葡萄’拆开导致葡萄无法召回。"""
    import re

    terms = set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))
    for phrase in re.findall(r"[\u4e00-\u9fff]+", text):
        terms.update(phrase[index : index + 2] for index in range(len(phrase) - 1))
    return terms


def searchable_text(record: dict) -> str:
    """冲突正文不表态，但候选值仍需可检索，才能承接用户的澄清。"""
    parts = [record.get("text", ""), record.get("key", "")]
    for atom in record.get("atoms", []):
        parts.extend([atom["slot"], atom["text"]])
        parts.extend(a["text"] for a in atom.get("alternatives", []))
        parts.extend(a["text"] for a in atom.get("history", []))
    return " ".join(parts)


def project_facts(record: dict, query: str) -> list[dict]:
    """按事实投影，未解决矛盾只作为待澄清信息；旧值仅用于明确的历史查询。"""
    import re

    history_requested = bool(
        re.search(r"以前|过去|去年|历史|曾经|当时|之前|20\d{2}年", query)
    )
    projected = []
    for atom in record.get("atoms", []):
        if atom.get("temporal_scope") == "historical" and not history_requested:
            continue
        fact = {
            k: atom[k]
            for k in (
                "slot",
                "text",
                "state",
                "conditions",
                "temporal_scope",
                "time_evidence",
                "valid_from",
            )
            if k in atom
        }
        if atom.get("state") == "conflicted":
            fact["alternatives"] = [a["text"] for a in atom.get("alternatives", [])]
        projected.append(fact)
        if history_requested:
            projected.extend(
                {
                    "slot": atom["slot"],
                    "text": old["text"],
                    "temporal_scope": "historical",
                    "valid_to": old.get("valid_to"),
                }
                for old in atom.get("history", [])
            )
    terms = query_terms(query)
    projected.sort(
        key=lambda a: len(terms & query_terms(json.dumps(a, ensure_ascii=False))),
        reverse=True,
    )
    return projected
