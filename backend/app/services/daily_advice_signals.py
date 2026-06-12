"""今日建议候选信号管线。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

DailyAdviceCategory = Literal[
    "weather",
    "operation",
    "crop_stage",
    "finance",
    "setup",
    "record",
]

_CATEGORY_ORDER: dict[DailyAdviceCategory, int] = {
    "weather": 0,
    "finance": 1,
    "operation": 2,
    "crop_stage": 3,
    "setup": 4,
    "record": 5,
}

_CATEGORY_LIMITS: dict[DailyAdviceCategory, int] = {
    "weather": 1,
    "finance": 1,
    "operation": 2,
    "crop_stage": 2,
    "setup": 1,
    "record": 1,
}


@dataclass(slots=True)
class DailyAdviceCandidate:
    """今日建议生成前的结构化候选。"""

    id: str
    category: DailyAdviceCategory
    title_hint: str
    detail_hint: str
    priority: int
    due_date: date | None
    source_type: str
    source_id: str | None
    dedupe_key: str
    reason: str

    def to_meta(self) -> dict[str, Any]:
        """输出可稳定序列化的候选元数据。"""
        return {
            "id": self.id,
            "category": self.category,
            "title_hint": self.title_hint,
            "detail_hint": self.detail_hint,
            "priority": self.priority,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "dedupe_key": self.dedupe_key,
            "reason": self.reason,
        }


def rank_daily_advice_candidates(
    candidates: list[DailyAdviceCandidate],
    *,
    today: date | None = None,
    limit: int = 3,
) -> list[DailyAdviceCandidate]:
    """排序、去重并按类别抑制今日建议候选。"""
    if limit <= 0:
        return []

    reference_day = today or date.today()
    ranked = sorted(candidates, key=lambda item: _candidate_sort_key(item, reference_day))
    selected: list[DailyAdviceCandidate] = []
    seen_dedupe_keys: set[str] = set()
    category_counts: dict[DailyAdviceCategory, int] = {
        category: 0 for category in _CATEGORY_LIMITS
    }

    for candidate in ranked:
        if candidate.dedupe_key in seen_dedupe_keys:
            continue

        category_limit = _CATEGORY_LIMITS[candidate.category]
        if category_counts[candidate.category] >= category_limit:
            continue

        selected.append(candidate)
        seen_dedupe_keys.add(candidate.dedupe_key)
        category_counts[candidate.category] += 1

        if len(selected) >= limit:
            break

    return selected


def render_candidate_context(candidates: list[DailyAdviceCandidate]) -> str:
    """渲染给大模型使用的今日行动候选上下文。"""
    if not candidates:
        return "今日无明确高优先级行动候选。"

    lines = ["【今日行动候选】"]
    for index, candidate in enumerate(candidates, start=1):
        due = candidate.due_date.isoformat() if candidate.due_date else "none"
        lines.append(
            f"{index}. priority={candidate.priority} "
            f"category={candidate.category} "
            f"source={candidate.category} "
            f"due={due} "
            f"title={candidate.title_hint} "
            f"detail={candidate.detail_hint} "
            f"reason={candidate.reason}"
        )

    return "\n".join(lines)


def fingerprint_candidates(candidates: list[DailyAdviceCandidate]) -> str:
    """为候选集合生成稳定短指纹。"""
    payload = [candidate.to_meta() for candidate in candidates]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _candidate_sort_key(
    candidate: DailyAdviceCandidate,
    today: date,
) -> tuple[int, int, int, str]:
    due_offset = (candidate.due_date - today).days if candidate.due_date else 0
    return (
        candidate.priority,
        due_offset,
        _CATEGORY_ORDER[candidate.category],
        candidate.id,
    )
