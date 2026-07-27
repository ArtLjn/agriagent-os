"""Operation 级多路混合候选召回。"""

from __future__ import annotations

import math
import logging
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from app.agent.router.models import ToolCandidate
from app.infra.trace_context import get_trace
from app.shared.logging import log_event


EmbedFn = Callable[[str], list[float]]
logger = logging.getLogger(__name__)


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

_LOW_SIGNAL_TERMS = {
    "今天",
    "昨天",
    "前天",
    "现在",
    "当前",
    "最近",
    "本周",
    "这周",
    "本月",
    "这个月",
    "查询",
    "查看",
    "看看",
    "看一下",
    "有哪些",
    "有哪",
    "哪些",
    "多少",
    "列表",
    "明细",
    "统计",
    "show",
    "list",
    "what",
    "which",
}

_TOKEN_ALIASES = {
    "debt": "欠款",
    "debts": "欠款",
    "owe": "欠",
    "owed": "欠",
    "payable": "应付",
    "payables": "应付",
    "unpaid": "未付",
    "wage": "工资",
    "wages": "工资",
    "salary": "工资",
    "payroll": "工资",
    "labor": "人工",
    "worker": "工人",
    "workers": "工人",
    "cost": "成本",
    "expense": "支出",
    "bill": "账单",
    "bills": "账单",
    "未结清": "欠款",
    "没结清": "欠款",
    "欠账": "欠款",
    "债务": "欠款",
    "greenhouse": "棚",
    "plot": "地块",
    "field": "地块",
    "weather": "天气",
}


@dataclass(frozen=True)
class HybridRetrievalResult:
    """混合召回结果。"""

    selected_names: list[str]
    selected_candidates: list[ToolCandidate] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, dict] = field(default_factory=dict)


@dataclass(frozen=True)
class _CandidateSignals:
    route_key: str
    bm25: float
    embedding: float
    lexical: float
    registry_prior: float
    anti_penalty: float
    low_signal_only_penalty: float
    score: float
    sources: tuple[str, ...]
    lexical_hits: tuple[str, ...]
    low_signal_hits: tuple[str, ...]
    anti_hits: tuple[str, ...]


class HybridOperationRetriever:
    """BM25、强词法信号和 embedding 并集召回后统一重排。"""

    min_score: float = 0.05

    def __init__(self, embed: EmbedFn | None = None) -> None:
        self._embed = embed
        self._embedding_cache: dict[str, list[float]] = {}

    def retrieve(
        self,
        message: str,
        candidates: list[ToolCandidate],
        *,
        limit: int = 5,
    ) -> HybridRetrievalResult:
        enabled_candidates = [candidate for candidate in candidates if candidate.enabled]
        if not enabled_candidates:
            return HybridRetrievalResult(selected_names=[])

        query_terms = _normalize_terms(message)
        bm25_scores = _bm25_scores(query_terms, enabled_candidates)
        embedding_scores = self._embedding_scores(message, enabled_candidates)
        max_bm25 = max(bm25_scores.values(), default=0.0)

        scored = [
            self._score_candidate(
                candidate,
                query_terms,
                bm25_scores.get(_route_key(candidate), 0.0),
                max_bm25,
                embedding_scores.get(_route_key(candidate), 0.0),
            )
            for candidate in enabled_candidates
        ]
        kept = [
            (candidate, signals)
            for candidate, signals in zip(enabled_candidates, scored, strict=True)
            if signals.score >= self.min_score and signals.sources
        ]
        kept.sort(
            key=lambda item: (
                -item[1].score,
                item[0].risk != "read",
                item[0].name,
                item[0].operation or "",
            )
        )
        selected = kept[:limit]
        return HybridRetrievalResult(
            selected_names=[candidate.name for candidate, _signals in selected],
            selected_candidates=[candidate for candidate, _signals in selected],
            scores={signals.route_key: signals.score for _candidate, signals in kept},
            evidence={
                signals.route_key: _evidence(signals)
                for _candidate, signals in kept
            },
        )

    def _score_candidate(
        self,
        candidate: ToolCandidate,
        query_terms: set[str],
        bm25: float,
        max_bm25: float,
        embedding: float,
    ) -> _CandidateSignals:
        route_key = _route_key(candidate)
        lexical_hits, low_signal_hits = _lexical_hits(query_terms, candidate)
        anti_hits = _anti_hits(query_terms, candidate)
        lexical = min(1.0, len(lexical_hits) * 0.45)
        registry_prior = _registry_prior(candidate)
        bm25_norm = bm25 / max_bm25 if max_bm25 > 0 else 0.0
        anti_penalty = min(0.8, len(anti_hits) * 0.35)
        low_signal_only_penalty = (
            0.25 if low_signal_hits and not lexical_hits and bm25_norm > 0 else 0.0
        )
        score = (
            0.35 * bm25_norm
            + 0.35 * max(0.0, embedding)
            + 0.20 * lexical
            + 0.10 * registry_prior
            - anti_penalty
            - low_signal_only_penalty
        )
        sources = _sources(
            strong_rule=bool(lexical_hits),
            bm25=bm25 > 0,
            embedding=embedding > 0,
        )
        return _CandidateSignals(
            route_key=route_key,
            bm25=bm25_norm,
            embedding=embedding,
            lexical=lexical,
            registry_prior=registry_prior,
            anti_penalty=anti_penalty,
            low_signal_only_penalty=low_signal_only_penalty,
            score=score,
            sources=sources,
            lexical_hits=tuple(sorted(lexical_hits)),
            low_signal_hits=tuple(sorted(low_signal_hits)),
            anti_hits=tuple(sorted(anti_hits)),
        )

    def _embedding_scores(
        self,
        message: str,
        candidates: list[ToolCandidate],
    ) -> dict[str, float]:
        if self._embed is None:
            return {}
        started_at = time.perf_counter()
        try:
            query_vector = self._embed(message)
        except (OSError, ValueError, RuntimeError) as exc:
            _log_embedding_recall(
                status="fallback",
                started_at=started_at,
                candidate_count=len(candidates),
                doc_embedding_calls=0,
                cache_hits=0,
                failed_docs=0,
                scored_count=0,
                error_code=exc.__class__.__name__,
            )
            return {}
        scores: dict[str, float] = {}
        doc_embedding_calls = 0
        cache_hits = 0
        failed_docs = 0
        for candidate in candidates:
            try:
                doc_text = _document_text(candidate)
                doc_vector = self._embedding_cache.get(doc_text)
                if doc_vector is None:
                    doc_embedding_calls += 1
                    doc_vector = self._embed(doc_text)
                    self._embedding_cache[doc_text] = doc_vector
                else:
                    cache_hits += 1
            except (OSError, ValueError, RuntimeError):
                failed_docs += 1
                continue
            scores[_route_key(candidate)] = max(
                0.0,
                _cosine(query_vector, doc_vector),
            )
        _log_embedding_recall(
            status="success" if scores else "empty",
            started_at=started_at,
            candidate_count=len(candidates),
            doc_embedding_calls=doc_embedding_calls,
            cache_hits=cache_hits,
            failed_docs=failed_docs,
            scored_count=len(scores),
        )
        return scores


def _route_key(candidate: ToolCandidate) -> str:
    if candidate.operation:
        return f"{candidate.name}.{candidate.operation}"
    return candidate.name


def _normalize_terms(text: str) -> set[str]:
    lower = text.lower()
    raw_terms = {
        token
        for token in re.findall(r"[a-z0-9_]+|[\u4e00-\u9fa5]+", lower)
        if token and token not in _STOP_TERMS
    }
    expanded = set(raw_terms)
    for token in raw_terms:
        if "_" in token:
            expanded.update(part for part in token.split("_") if part)
        alias = _TOKEN_ALIASES.get(token)
        if alias:
            expanded.add(alias)
        for part in token.split("_"):
            alias = _TOKEN_ALIASES.get(part)
            if alias:
                expanded.add(alias)
        if re.fullmatch(r"[\u4e00-\u9fa5]+", token):
            expanded.update(_char_ngrams(token))
    for token, alias in _TOKEN_ALIASES.items():
        if token in lower:
            expanded.add(alias)
    return expanded


def _char_ngrams(value: str) -> set[str]:
    if len(value) <= 2:
        return {value}
    grams = {value}
    for size in (2, 3, 4):
        for start in range(0, len(value) - size + 1):
            grams.add(value[start : start + size])
    return grams


def _candidate_terms(candidate: ToolCandidate) -> Counter[str]:
    terms: Counter[str] = Counter()
    _add_weighted_terms(
        terms,
        [candidate.operation or "", candidate.legacy_alias or "", *candidate.intents],
        3.0,
    )
    _add_weighted_terms(terms, candidate.entities, 2.5)
    _add_weighted_terms(terms, candidate.trigger_examples, 1.5)
    _add_weighted_terms(
        terms,
        [candidate.name, candidate.capability or "", candidate.domain],
        1.0,
    )
    return terms


def _add_weighted_terms(
    terms: Counter[str],
    values: list[str],
    weight: float,
) -> None:
    for value in values:
        for term in _normalize_terms(value):
            terms[term] += weight


def _bm25_scores(
    query_terms: set[str],
    candidates: list[ToolCandidate],
) -> dict[str, float]:
    doc_terms = {
        _route_key(candidate): _candidate_terms(candidate) for candidate in candidates
    }
    doc_count = len(candidates)
    if not query_terms or doc_count == 0:
        return {}
    avg_len = sum(sum(terms.values()) for terms in doc_terms.values()) / doc_count
    scores: dict[str, float] = {}
    for route_key, terms in doc_terms.items():
        doc_len = sum(terms.values()) or 1.0
        score = 0.0
        for term in query_terms:
            tf = terms.get(term, 0.0)
            if tf <= 0:
                continue
            df = sum(1 for item in doc_terms.values() if item.get(term, 0.0) > 0)
            idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
            score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * doc_len / avg_len))
        scores[route_key] = score
    return scores


def _lexical_hits(
    query_terms: set[str],
    candidate: ToolCandidate,
) -> tuple[set[str], set[str]]:
    candidate_terms = _candidate_terms(candidate)
    lexical_hits: set[str] = set()
    low_signal_hits: set[str] = set()
    for term in query_terms:
        if not term or candidate_terms.get(term, 0.0) <= 0:
            continue
        if term in _LOW_SIGNAL_TERMS:
            low_signal_hits.add(term)
        else:
            lexical_hits.add(term)
    return lexical_hits, low_signal_hits


def _anti_hits(query_terms: set[str], candidate: ToolCandidate) -> set[str]:
    if not candidate.anti_examples:
        return set()
    anti_text = " ".join(candidate.anti_examples).lower()
    return {
        term
        for term in query_terms
        if term and term not in _LOW_SIGNAL_TERMS and term in anti_text
    }


def _document_text(candidate: ToolCandidate) -> str:
    values = [
        candidate.name,
        candidate.domain,
        candidate.capability or "",
        candidate.operation or "",
        candidate.legacy_alias or "",
        *candidate.intents,
        *candidate.entities,
        *candidate.trigger_examples,
    ]
    return " ".join(value for value in values if value)


def _registry_prior(candidate: ToolCandidate) -> float:
    prior = 0.5
    if candidate.operation:
        prior += 0.2
    if candidate.risk == "read":
        prior += 0.2
    if candidate.capability:
        prior += 0.1
    return min(1.0, prior)


def _sources(*, strong_rule: bool, bm25: bool, embedding: bool) -> tuple[str, ...]:
    sources = []
    if strong_rule:
        sources.append("strong_rule")
    if bm25:
        sources.append("bm25")
    if embedding:
        sources.append("embedding")
    return tuple(sources)


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _evidence(signals: _CandidateSignals) -> dict:
    return {
        "score": signals.score,
        "sources": list(signals.sources),
        "bm25": signals.bm25,
        "embedding": signals.embedding,
        "lexical": signals.lexical,
        "registry_prior": signals.registry_prior,
        "anti_penalty": signals.anti_penalty,
        "low_signal_only_penalty": signals.low_signal_only_penalty,
        "lexical_hits": list(signals.lexical_hits),
        "low_signal_hits": list(signals.low_signal_hits),
        "anti_hits": list(signals.anti_hits),
    }


def _log_embedding_recall(
    *,
    status: str,
    started_at: float,
    candidate_count: int,
    doc_embedding_calls: int,
    cache_hits: int,
    failed_docs: int,
    scored_count: int,
    error_code: str | None = None,
) -> None:
    trace = get_trace()
    log_event(
        logger,
        logging.INFO if status in {"success", "empty"} else logging.WARNING,
        "skill_router_embedding_recall_completed",
        code=error_code,
        request_id=trace.request_id if trace else None,
        session_id=trace.session_id if trace else None,
        status=status,
        duration_ms=int((time.perf_counter() - started_at) * 1000),
        data={
            "candidate_count": candidate_count,
            "doc_embedding_calls": doc_embedding_calls,
            "cache_hits": cache_hits,
            "failed_docs": failed_docs,
            "scored_count": scored_count,
        },
    )
