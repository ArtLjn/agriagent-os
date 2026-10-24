"""主题记忆内的原子事实：只更新目标事实，来源与时序不随整段文字漂移。"""

from __future__ import annotations

from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field

from agent.domains.harness.memory.personalization import MemoryError, now

MAX_FACTS_PER_MEMORY = 30
MAX_EVIDENCE_TURNS = 100


class AtomicFact(BaseModel):
    """slot 标识同一对象与属性；text 保留值、否定和适用条件。"""

    model_config = ConfigDict(extra="forbid", strict=True)
    slot: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=1, max_length=500)


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
    if candidate.target_slot and atom is None:
        raise MemoryError("memory_fact_not_found", "目标事实已变化，请重新读取")
    observed_at = task.get("observed_at", 0)
    explicit = task.get("source_type") == "explicit"
    repeated_turn = bool(atom and task["turn_id"] in atom.get("evidence_turns", []))
    if atom:
        # 后台可能先于显式工具落库；本轮显式保存可提升来源，但不能重复累计证据。
        if repeated_turn and (not explicit or atom["source_type"] == "explicit"):
            return False
        if repeated_turn and candidate.relation == "contradict":
            raise MemoryError(
                "memory_same_turn_conflict", "同一轮事实出现不同取值，需重新核对"
            )
        if observed_at < atom.get("last_observed_at", 0):
            return False
        if atom["source_type"] == "explicit" and not explicit:
            from datetime import datetime

            if (
                candidate.relation != "contradict"
                or observed_at <= datetime.fromisoformat(atom["updated_at"]).timestamp()
            ):
                return False
        if candidate.relation == "merge":
            raise MemoryError("memory_fact_conflict", "不同事实不能覆盖同一事实槽位")
    else:
        if len(atoms) >= MAX_FACTS_PER_MEMORY:
            raise MemoryError("memory_fact_limit", "主题内事实已达上限")
        atom = {"slot": slot, "revision": 0, "evidence_turns": []}
        atoms.append(atom)
    changed_value = candidate.relation == "contradict" or atom["revision"] == 0
    # 过去支持旧值的证据不能为相反的新值增加置信度；不保存被替换的正文副本。
    turns = [] if changed_value else atom.get("evidence_turns", [])
    turns = list(dict.fromkeys([*turns, task["turn_id"]]))[-MAX_EVIDENCE_TURNS:]
    atom.update(
        text=atom.get("text", candidate.text)
        if candidate.relation == "reinforce"
        else candidate.text,
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
    if len(text) > 500:
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
