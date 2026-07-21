"""Registry metadata 驱动的轻量候选召回。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agent.router.models import ToolCandidate


_TOKEN_ALIASES = {
    "add": "新增",
    "bill": "账单",
    "cost": "成本",
    "create": "创建",
    "debt": "欠款",
    "delete": "删除",
    "expense": "支出",
    "labor": "人工",
    "owe": "欠",
    "owed": "欠",
    "payable": "应付",
    "payables": "应付",
    "payroll": "工资",
    "record": "记录",
    "remain": "剩余",
    "remaining": "剩余",
    "remove": "删除",
    "salary": "工资",
    "unpaid": "未付",
    "wage": "工资",
    "wages": "工资",
    "worker": "工人",
    "workers": "工人",
}

_STOP_TERMS = {
    "a",
    "an",
    "and",
    "are",
    "for",
    "how",
    "i",
    "is",
    "me",
    "much",
    "my",
    "of",
    "please",
    "the",
    "to",
}


@dataclass(frozen=True)
class CandidateRetrievalResult:
    """候选召回结果。"""

    selected_names: list[str]
    scores: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, dict] = field(default_factory=dict)


class CandidateRetriever:
    """根据 ToolCandidate metadata 对候选工具打分。"""

    min_score: float = 1.0

    def retrieve(
        self,
        message: str,
        candidates: list[ToolCandidate],
        *,
        limit: int = 3,
    ) -> CandidateRetrievalResult:
        terms = _normalize_terms(message)
        scored = [
            self._score_candidate(candidate, terms)
            for candidate in candidates
            if candidate.enabled
        ]
        kept = [item for item in scored if item[1] >= self.min_score]
        kept.sort(key=lambda item: (-item[1], item[0].risk != "read", item[0].name))
        selected = kept[:limit]
        return CandidateRetrievalResult(
            selected_names=[
                candidate.name for candidate, _score, _evidence in selected
            ],
            scores={candidate.name: score for candidate, score, _evidence in scored},
            evidence={
                candidate.name: evidence for candidate, _score, evidence in selected
            },
        )

    def _score_candidate(
        self,
        candidate: ToolCandidate,
        terms: set[str],
    ) -> tuple[ToolCandidate, float, dict]:
        tag_hits = _hits(terms, candidate.entities)
        intent_hits = _hits(terms, candidate.intents, min_hits=2)
        example_hits = _hits(terms, candidate.trigger_examples, min_hits=2)
        anti_hits = _hits(terms, candidate.anti_examples, min_hits=2)
        identity_hits = _hits(
            terms,
            [
                candidate.name,
                candidate.domain,
                candidate.capability or "",
                candidate.operation or "",
                candidate.legacy_alias or "",
            ],
            min_hits=2,
        )
        score = (
            len(example_hits) * 2.0
            + len(tag_hits) * 1.5
            + len(intent_hits) * 1.0
            + len(identity_hits) * 0.5
            - len(anti_hits) * 3.0
        )
        if candidate.risk == "read":
            score += 0.2
        return (
            candidate,
            score,
            {
                "tag_hits": tag_hits,
                "intent_hits": intent_hits,
                "example_hits": example_hits,
                "anti_hits": anti_hits,
                "identity_hits": identity_hits,
                "score": score,
            },
        )


def _normalize_terms(text: str) -> set[str]:
    lower = text.lower()
    terms = {
        token
        for token in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fa5]+", lower)
        if token and token not in _STOP_TERMS
    }
    expanded = set(terms)
    for token in terms:
        alias = _TOKEN_ALIASES.get(token)
        if alias:
            expanded.add(alias)
        if re.fullmatch(r"[\u4e00-\u9fa5]+", token):
            expanded.update(_char_ngrams(token))
    return expanded


def _char_ngrams(value: str) -> set[str]:
    if len(value) <= 2:
        return {value}
    grams = set()
    for size in (2, 3, 4):
        for start in range(0, len(value) - size + 1):
            grams.add(value[start : start + size])
    return grams


def _hits(terms: set[str], values: list[str], *, min_hits: int = 1) -> list[str]:
    hits = []
    for value in values:
        normalized = value.lower()
        hit_count = sum(1 for term in terms if term and term in normalized)
        if hit_count >= min_hits:
            hits.append(value)
    return hits
