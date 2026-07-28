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


VectorSearchFn = Callable[[str, list[ToolCandidate]], dict[str, float]]
logger = logging.getLogger(__name__)
_SCORING_FORMULA = (
    "0.35*bm25 + 0.35*vector + 0.20*lexical + "
    "0.10*registry_prior + operation_prior - penalties"
)


_STOP_TERMS = frozenset("a an and are for how i is me much my of please the to".split())
_LOW_SIGNAL_TERMS = frozenset(
    "今天 昨天 前天 现在 当前 最近 本周 这周 本月 这个月 查询 查看 看看 "
    "看一下 我 我的 有哪些 有哪 哪些 多少 列表 明细 统计 show list what which".split()
)

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
    "expenses": "支出",
    "bill": "账单",
    "bills": "账单",
    "花费": "成本",
    "费用": "成本",
    "开销": "成本",
    "未结清": "欠款",
    "没结清": "欠款",
    "欠账": "欠款",
    "债务": "欠款",
    "greenhouse": "棚",
    "plot": "地块",
    "field": "地块",
    "weather": "天气",
}

_COST_SUMMARY_QUERY_TERMS = frozenset(
    "余额 收支 成本 费用 花费 支出 收入 利润 账单 流水 多少钱 多少".split()
)
_COST_RECORD_WRITE_TERMS = frozenset(
    "买 卖 采购 购入 销售 收入 支出 花了 账单 记账".split()
)
_CATEGORY_MANAGEMENT_TERMS = frozenset("分类 类别 科目 category categories".split())
_COST_ANALYTICS_QUERY_TERMS = frozenset(
    "趋势 同比 环比 分析 比上个月 比去年".split()
)
_FARM_LOG_CREATE_TERMS = frozenset(
    "记录 记一下 浇水 施肥 打药 除草 翻地 育苗 农事 操作".split()
)
_WORK_ORDER_CREATE_TERMS = frozenset("安排 派 叫 让 用工 作业单 工人 干活".split())
_UPDATE_DELETE_TERMS = frozenset("修改 更新 删除 删掉 更正 纠正 改成 改为".split())


@dataclass(frozen=True)
class HybridRetrievalResult:
    """混合召回结果。"""

    selected_names: list[str]
    selected_candidates: list[ToolCandidate] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    evidence: dict[str, dict] = field(default_factory=dict)
    recall: dict = field(default_factory=dict)
    top_candidates: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class _VectorRecallResult:
    """外部向量召回状态。"""

    scores: dict[str, float]
    status: str
    vector_search_used: bool
    error_code: str | None = None


@dataclass(frozen=True)
class _CandidateSignals:
    route_key: str
    bm25: float
    vector: float
    lexical: float
    registry_prior: float
    operation_prior: float
    anti_penalty: float
    low_signal_only_penalty: float
    score: float
    sources: tuple[str, ...]
    lexical_hits: tuple[str, ...]
    low_signal_hits: tuple[str, ...]
    anti_hits: tuple[str, ...]


class HybridOperationRetriever:
    """BM25、强词法信号和外部向量检索并集召回后统一重排。"""

    min_score: float = 0.05

    def __init__(
        self,
        vector_search: VectorSearchFn | None = None,
    ) -> None:
        self._vector_search = vector_search

    @property
    def vector_index_enabled(self) -> bool:
        return self._vector_search is not None

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
        vector_recall = self._vector_scores(message, enabled_candidates)
        vector_scores = vector_recall.scores
        max_bm25 = max(bm25_scores.values(), default=0.0)

        scored = [
            self._score_candidate(
                candidate,
                query_terms,
                bm25_scores.get(_route_key(candidate), 0.0),
                max_bm25,
                vector_scores.get(_route_key(candidate), 0.0),
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
        _log_candidate_scores(
            candidate_count=len(enabled_candidates),
            ranked=kept,
            limit=min(max(limit, 5), 8),
        )
        selected = kept[:limit]
        top_candidates = [
            _candidate_score_log_item(candidate, signals)
            for candidate, signals in kept[: min(max(limit, 5), 8)]
        ]
        return HybridRetrievalResult(
            selected_names=[candidate.name for candidate, _signals in selected],
            selected_candidates=[candidate for candidate, _signals in selected],
            scores={signals.route_key: signals.score for _candidate, signals in kept},
            evidence={
                signals.route_key: _evidence(signals)
                for _candidate, signals in kept
            },
            recall=_recall_summary(
                candidate_count=len(enabled_candidates),
                scored_count=len(kept),
                vector_recall=vector_recall,
                bm25_used=any(score > 0 for score in bm25_scores.values()),
            ),
            top_candidates=top_candidates,
        )

    def _score_candidate(
        self,
        candidate: ToolCandidate,
        query_terms: set[str],
        bm25: float,
        max_bm25: float,
        vector: float,
    ) -> _CandidateSignals:
        route_key = _route_key(candidate)
        lexical_hits, low_signal_hits = _lexical_hits(query_terms, candidate)
        anti_hits = _anti_hits(query_terms, candidate)
        lexical = min(1.0, len(lexical_hits) * 0.45)
        registry_prior = _registry_prior(candidate)
        operation_prior = _operation_prior(candidate, query_terms)
        bm25_norm = bm25 / max_bm25 if max_bm25 > 0 else 0.0
        anti_penalty = min(0.8, len(anti_hits) * 0.35)
        low_signal_only_penalty = (
            0.25 if low_signal_hits and not lexical_hits and bm25_norm > 0 else 0.0
        )
        score = (
            0.35 * bm25_norm
            + 0.35 * max(0.0, vector)
            + 0.20 * lexical
            + 0.10 * registry_prior
            + operation_prior
            - anti_penalty
            - low_signal_only_penalty
        )
        sources = _sources(
            strong_rule=bool(lexical_hits),
            bm25=bm25 > 0,
            vector=vector > 0,
        )
        return _CandidateSignals(
            route_key=route_key,
            bm25=bm25_norm,
            vector=vector,
            lexical=lexical,
            registry_prior=registry_prior,
            operation_prior=operation_prior,
            anti_penalty=anti_penalty,
            low_signal_only_penalty=low_signal_only_penalty,
            score=score,
            sources=sources,
            lexical_hits=tuple(sorted(lexical_hits)),
            low_signal_hits=tuple(sorted(low_signal_hits)),
            anti_hits=tuple(sorted(anti_hits)),
        )

    def _vector_scores(
        self,
        message: str,
        candidates: list[ToolCandidate],
    ) -> _VectorRecallResult:
        if self._vector_search is None:
            _log_missing_vector_index(candidate_count=len(candidates))
            return _VectorRecallResult(
                scores={},
                status="missing_index",
                vector_search_used=False,
            )
        started_at = time.perf_counter()
        try:
            raw_scores = self._vector_search(message, candidates)
        except (OSError, ValueError, RuntimeError) as exc:
            _log_vector_recall(
                status="fallback",
                started_at=started_at,
                candidate_count=len(candidates),
                local_query_embedding_calls=0,
                local_doc_embedding_calls=0,
                cache_hits=0,
                vector_search_calls=1,
                failed_docs=0,
                scored_count=0,
                error_code=exc.__class__.__name__,
            )
            return _VectorRecallResult(
                scores={},
                status="fallback",
                vector_search_used=True,
                error_code=exc.__class__.__name__,
            )
        scores = _valid_vector_scores(raw_scores, candidates)
        status = "success" if scores else "empty"
        _log_vector_recall(
            status=status,
            started_at=started_at,
            candidate_count=len(candidates),
            local_query_embedding_calls=0,
            local_doc_embedding_calls=0,
            cache_hits=0,
            vector_search_calls=1,
            failed_docs=0,
            scored_count=len(scores),
        )
        return _VectorRecallResult(
            scores=scores,
            status=status,
            vector_search_used=True,
        )


def _log_missing_vector_index(*, candidate_count: int) -> None:
    _log_vector_recall(
        status="missing_index",
        started_at=time.perf_counter(),
        candidate_count=candidate_count,
        local_query_embedding_calls=0,
        local_doc_embedding_calls=0,
        cache_hits=0,
        vector_search_calls=0,
        failed_docs=0,
        scored_count=0,
    )


def _log_candidate_scores(
    *,
    candidate_count: int,
    ranked: list[tuple[ToolCandidate, _CandidateSignals]],
    limit: int,
) -> None:
    if not ranked:
        return
    trace = get_trace()
    log_event(
        logger,
        logging.INFO,
        "skill_router_candidate_scores",
        request_id=trace.request_id if trace else None,
        session_id=trace.session_id if trace else None,
        status="ranked",
        data={
            "candidate_count": candidate_count,
            "scored_count": len(ranked),
            "shown_count": min(len(ranked), limit),
            "top_routes": [signals.route_key for _, signals in ranked[:limit]],
            "top_score": _round_score(ranked[0][1].score),
            "scoring_formula": _SCORING_FORMULA,
        },
    )
    logger.info(
        "event=skill_router_candidate_scores_detail\n%s",
        _format_candidate_scores_block(
            candidate_count=candidate_count,
            ranked=ranked,
            limit=limit,
        ),
    )


def _candidate_score_log_item(
    candidate: ToolCandidate,
    signals: _CandidateSignals,
) -> dict:
    return {
        "route": signals.route_key,
        "skill": candidate.name,
        "domain": candidate.domain,
        "capability": candidate.capability,
        "operation": candidate.operation,
        "risk": candidate.risk,
        "score": _round_score(signals.score),
        "bm25": _round_score(signals.bm25),
        "vector": _round_score(signals.vector),
        "lexical": _round_score(signals.lexical),
        "registry_prior": _round_score(signals.registry_prior),
        "operation_prior": _round_score(signals.operation_prior),
        "anti_penalty": _round_score(signals.anti_penalty),
        "low_signal_penalty": _round_score(signals.low_signal_only_penalty),
        "sources": list(signals.sources),
        "lexical_hits": list(signals.lexical_hits[:5]),
        "low_signal_hits": list(signals.low_signal_hits[:5]),
        "anti_hits": list(signals.anti_hits[:5]),
    }


def _round_score(value: float) -> float:
    return round(float(value), 4)


def _format_candidate_scores_block(
    *,
    candidate_count: int,
    ranked: list[tuple[ToolCandidate, _CandidateSignals]],
    limit: int,
) -> str:
    shown = ranked[:limit]
    lines = [
        "Skill Router Candidate Scores",
        f"  formula: {_SCORING_FORMULA}",
        f"  candidates: total={candidate_count} scored={len(ranked)} shown={len(shown)}",
        "  top:",
    ]
    for index, (candidate, signals) in enumerate(shown, start=1):
        lines.append(
            "    "
            f"{index}. {signals.route_key} "
            f"final={_round_score(signals.score):.4f} "
            f"bm25={_round_score(signals.bm25):.4f} "
            f"vector={_round_score(signals.vector):.4f} "
            f"lexical={_round_score(signals.lexical):.4f} "
            f"registry={_round_score(signals.registry_prior):.4f} "
            f"operation={_round_score(signals.operation_prior):.4f} "
            "penalty="
            f"{_round_score(signals.anti_penalty + signals.low_signal_only_penalty):.4f}"
        )
        lines.append(
            "       "
            f"skill={candidate.name} domain={candidate.domain} "
            f"risk={candidate.risk} sources={_format_signal_values(signals.sources)}"
        )
        hits = _format_signal_hits(signals)
        if hits:
            lines.append(f"       hits: {hits}")
    return "\n".join(lines)


def _format_signal_values(values: set[str] | list[str] | tuple[str, ...]) -> str:
    return ",".join(str(value) for value in values) if values else "-"


def _format_signal_hits(signals: _CandidateSignals) -> str:
    parts = []
    for label, values in (
        ("lexical", signals.lexical_hits[:5]),
        ("low_signal", signals.low_signal_hits[:5]),
        ("anti", signals.anti_hits[:5]),
    ):
        if values:
            parts.append(f"{label}={_format_signal_values(values)}")
    return " ".join(parts)


def _recall_summary(
    *,
    candidate_count: int,
    scored_count: int,
    vector_recall: _VectorRecallResult,
    bm25_used: bool,
) -> dict:
    return {
        "path": "bm25_vector_hybrid",
        "retrieval_engine": "hybrid_operation_retriever",
        "candidate_count": candidate_count,
        "scored_count": scored_count,
        "bm25_used": bm25_used,
        "vector_index_enabled": vector_recall.status != "missing_index",
        "vector_search_used": vector_recall.vector_search_used,
        "rag_service_used": vector_recall.vector_search_used,
        "quillrag_retrieve_used": vector_recall.vector_search_used,
        "external_embedding_requested": vector_recall.vector_search_used,
        "embedding_location": "quillrag_service"
        if vector_recall.vector_search_used
        else "none",
        "local_embedding_used": False,
        "local_query_embedding_calls": 0,
        "local_doc_embedding_calls": 0,
        "vector_status": vector_recall.status,
        "vector_scored_count": len(vector_recall.scores),
        "vector_error_code": vector_recall.error_code,
        "scoring_formula": (
            "0.35*bm25 + 0.35*vector + 0.20*lexical + "
            "0.10*registry_prior + operation_prior - penalties"
        ),
    }


def _valid_vector_scores(
    raw_scores: dict[str, float],
    candidates: list[ToolCandidate],
) -> dict[str, float]:
    candidate_keys = {_route_key(candidate) for candidate in candidates}
    return {
        route_key: max(0.0, float(score))
        for route_key, score in raw_scores.items()
        if route_key in candidate_keys
    }


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


def _registry_prior(candidate: ToolCandidate) -> float:
    prior = 0.5
    if candidate.operation:
        prior += 0.2
    if candidate.risk == "read":
        prior += 0.2
    if candidate.capability:
        prior += 0.1
    return min(1.0, prior)


def _operation_prior(candidate: ToolCandidate, query_terms: set[str]) -> float:
    alias_prior = 0.03 if candidate.legacy_alias == candidate.name else 0.0
    if candidate.capability == "manage_farm_logs":
        if query_terms & _COST_RECORD_WRITE_TERMS:
            return -0.22 + alias_prior
        if candidate.operation == "create_log" and query_terms & _FARM_LOG_CREATE_TERMS:
            return 0.08 + alias_prior
        if candidate.operation == "manage_log" and not (
            query_terms & _UPDATE_DELETE_TERMS
        ):
            return -0.04 + alias_prior
        return alias_prior
    if candidate.capability == "manage_cost_categories" and not (
        query_terms & _CATEGORY_MANAGEMENT_TERMS
    ):
        return -0.12 + alias_prior
    if (
        candidate.capability == "manage_work_orders"
        and candidate.operation == "create_work_order"
        and query_terms & _WORK_ORDER_CREATE_TERMS
    ):
        return 0.16 + alias_prior
    if candidate.capability == "manage_planting_units" and (
        query_terms & _WORK_ORDER_CREATE_TERMS
    ):
        return -0.10 + alias_prior
    if candidate.capability != "manage_cost":
        return alias_prior
    if candidate.operation == "create_record" and (
        query_terms & _COST_RECORD_WRITE_TERMS
    ):
        return 0.36 + alias_prior
    if candidate.operation == "query_summary" and (
        query_terms & _COST_SUMMARY_QUERY_TERMS
    ):
        return 0.06 + alias_prior
    if candidate.operation == "analyze_cost" and not (
        query_terms & _COST_ANALYTICS_QUERY_TERMS
    ):
        return -0.04 + alias_prior
    return alias_prior


def _sources(*, strong_rule: bool, bm25: bool, vector: bool) -> tuple[str, ...]:
    sources = []
    if strong_rule:
        sources.append("strong_rule")
    if bm25:
        sources.append("bm25")
    if vector:
        sources.append("vector")
    return tuple(sources)


def _evidence(signals: _CandidateSignals) -> dict:
    return {
        "score": signals.score,
        "sources": list(signals.sources),
        "bm25": signals.bm25,
        "vector": signals.vector,
        "lexical": signals.lexical,
        "registry_prior": signals.registry_prior,
        "operation_prior": signals.operation_prior,
        "anti_penalty": signals.anti_penalty,
        "low_signal_only_penalty": signals.low_signal_only_penalty,
        "lexical_hits": list(signals.lexical_hits),
        "low_signal_hits": list(signals.low_signal_hits),
        "anti_hits": list(signals.anti_hits),
    }


def _log_vector_recall(
    *,
    status: str,
    started_at: float,
    candidate_count: int,
    local_query_embedding_calls: int,
    local_doc_embedding_calls: int,
    cache_hits: int,
    vector_search_calls: int,
    failed_docs: int,
    scored_count: int,
    error_code: str | None = None,
) -> None:
    trace = get_trace()
    log_event(
        logger,
        logging.INFO
        if status in {"success", "empty", "disabled", "missing_index"}
        else logging.WARNING,
        "skill_router_vector_recall_completed",
        code=error_code,
        request_id=trace.request_id if trace else None,
        session_id=trace.session_id if trace else None,
        status=status,
        duration_ms=int((time.perf_counter() - started_at) * 1000),
        data={
            "candidate_count": candidate_count,
            "vector_index_enabled": vector_search_calls > 0
            or status not in {"missing_index", "disabled"},
            "vector_search_used": vector_search_calls > 0,
            "quillrag_retrieve_used": vector_search_calls > 0,
            "external_embedding_requested": vector_search_calls > 0,
            "embedding_location": "quillrag_service"
            if vector_search_calls > 0
            else "none",
            "local_embedding_used": False,
            "local_query_embedding_calls": local_query_embedding_calls,
            "local_doc_embedding_calls": local_doc_embedding_calls,
            "cache_hits": cache_hits,
            "vector_search_calls": vector_search_calls,
            "failed_docs": failed_docs,
            "scored_count": scored_count,
        },
    )
