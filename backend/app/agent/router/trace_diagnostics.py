"""Skill Router trace 诊断证据构建。"""

from __future__ import annotations

from dataclasses import replace

from app.agent.router.models import RouterDecision


def selection_path(decision: RouterDecision) -> str:
    """返回本次 RouterDecision 的候选来源路径。"""

    if decision.fallback:
        return f"fallback:{decision.fallback}"
    frame_sources = [
        str(frame.evidence.get("source"))
        for frame in decision.frames
        if frame.evidence.get("source")
    ]
    if "hybrid_operation_retriever" in frame_sources:
        return "hybrid_retrieval"
    if "candidate_retriever" in frame_sources:
        return "write_candidate_retriever"
    if decision.frames:
        return "rule_classifier"
    return "policy"


def candidate_explanations(decision: RouterDecision) -> list[dict]:
    """返回被选中候选和混合召回 Top 候选的评分解释。"""

    selected = decision.evidence.get("selected_candidates")
    if not isinstance(selected, list):
        selected = []
    hybrid_top_candidates = _hybrid_top_candidates(decision)
    explanations = [
        _hybrid_candidate_explanation(item)
        for item in hybrid_top_candidates
        if isinstance(item, dict)
    ]
    selected_routes = {
        _candidate_route(item) for item in selected if isinstance(item, dict)
    }
    explained_routes = {
        str(item.get("route") or "") for item in explanations if isinstance(item, dict)
    }
    selected_explanations = [
        _candidate_explanation(decision, item)
        for item in selected
        if isinstance(item, dict) and _candidate_route(item) not in explained_routes
    ]
    if explanations:
        for item in explanations:
            route = str(item.get("route") or "")
            selected_by_policy = route in selected_routes
            item["selected"] = selected_by_policy
            item["why_selected"] = (
                f"混合召回候选 {route} 排名靠前并被 policy 选中"
                if selected_by_policy
                else f"混合召回 Top 候选 {route}，未进入最终工具绑定"
            )
        return explanations + selected_explanations
    return [
        _candidate_explanation(decision, item)
        for item in selected
        if isinstance(item, dict)
    ]


def with_trace_diagnostics(
    decision: RouterDecision,
    *,
    vector_index_enabled: bool,
) -> RouterDecision:
    """把召回路径、候选解释和评分摘要合并到 trace evidence。"""

    recall = _decision_recall_summary(
        decision,
        vector_index_enabled=vector_index_enabled,
    )
    explanations = candidate_explanations(decision)
    return replace(
        decision,
        evidence={
            **decision.evidence,
            "selection_path": selection_path(decision),
            "selection_reason": decision.reason,
            "recall": recall,
            "candidate_explanations": explanations,
        },
    )


def _candidate_explanation(decision: RouterDecision, candidate: dict) -> dict:
    skill = str(candidate.get("name") or "")
    capability = str(candidate.get("capability") or skill)
    operation = candidate.get("operation")
    route = _candidate_route(candidate)
    score_detail = _score_detail_for_candidate(
        decision,
        route=route,
        capability=capability,
        operation=str(operation or ""),
    )
    return {
        "route": route,
        "skill": skill,
        "operation": operation,
        "risk": candidate.get("risk"),
        "selected": True,
        "why_selected": _why_selected(decision, route, capability, operation),
        "scores": score_detail,
    }


def _hybrid_candidate_explanation(candidate: dict) -> dict:
    route = str(candidate.get("route") or "")
    return {
        "route": route,
        "skill": candidate.get("skill"),
        "domain": candidate.get("domain"),
        "capability": candidate.get("capability"),
        "operation": candidate.get("operation"),
        "risk": candidate.get("risk"),
        "selected": False,
        "why_selected": "混合召回候选，按 final_score 排序进入候选池",
        "scores": {
            "final": _round_log_score(candidate.get("score", 0.0)),
            "bm25": _round_log_score(candidate.get("bm25", 0.0)),
            "vector": _round_log_score(candidate.get("vector", 0.0)),
            "lexical": _round_log_score(candidate.get("lexical", 0.0)),
            "registry_prior": _round_log_score(
                candidate.get("registry_prior", 0.0)
            ),
            "operation_prior": _round_log_score(
                candidate.get("operation_prior", 0.0)
            ),
            "anti_penalty": _round_log_score(candidate.get("anti_penalty", 0.0)),
            "low_signal_penalty": _round_log_score(
                candidate.get("low_signal_penalty", 0.0)
            ),
            "sources": candidate.get("sources") or [],
            "lexical_hits": candidate.get("lexical_hits") or [],
            "low_signal_hits": candidate.get("low_signal_hits") or [],
            "anti_hits": candidate.get("anti_hits") or [],
        },
    }


def _candidate_route(candidate: dict) -> str:
    skill = str(candidate.get("name") or candidate.get("skill") or "")
    operation = candidate.get("operation")
    return f"{skill}.{operation}" if operation else skill


def _hybrid_top_candidates(decision: RouterDecision) -> list[dict]:
    for frame in decision.frames:
        top_candidates = frame.evidence.get("top_candidates")
        if isinstance(top_candidates, list):
            return top_candidates
    return []


def _score_detail_for_candidate(
    decision: RouterDecision,
    *,
    route: str,
    capability: str,
    operation: str,
) -> dict:
    for frame in decision.frames:
        evidence = frame.evidence
        retrieval_evidence = evidence.get("retrieval_evidence")
        if isinstance(retrieval_evidence, dict) and route in retrieval_evidence:
            return _compact_score_detail(retrieval_evidence[route])
        matched = _matched_candidate_score(evidence, capability, operation)
        if frame.capability == capability and (not operation or frame.operation == operation):
            matched["frame_score"] = _round_log_score(frame.score)
            matched["frame_confidence"] = _round_log_score(frame.confidence)
            if operation and not matched.get("operation"):
                matched["operation"] = _round_log_score(frame.score or frame.confidence)
        if matched:
            return matched
    return {
        "capability": _round_log_score(
            decision.scores.get("capability", {}).get(capability, 0.0)
        ),
        "operation": _round_log_score(
            decision.scores.get("operation", {}).get(operation, 0.0)
            if operation
            else 0.0
        ),
    }


def _compact_score_detail(raw: dict) -> dict:
    fields = (
        "score",
        "bm25",
        "vector",
        "lexical",
        "registry_prior",
        "operation_prior",
        "anti_penalty",
        "low_signal_only_penalty",
    )
    detail = {
        key: _round_log_score(raw.get(key, 0.0)) for key in fields if key in raw
    }
    if raw.get("sources"):
        detail["sources"] = raw["sources"]
    if raw.get("lexical_hits"):
        detail["lexical_hits"] = raw["lexical_hits"]
    return detail


def _matched_candidate_score(
    evidence: dict,
    capability: str,
    operation: str,
) -> dict:
    capability_scores = evidence.get("capability_scores")
    operation_scores = evidence.get("operation_scores")
    domain_scores = evidence.get("domain_scores")
    matched = evidence.get("matched_candidates")
    detail: dict = {}
    if isinstance(capability_scores, dict):
        detail["capability"] = _round_log_score(capability_scores.get(capability, 0.0))
    if isinstance(operation_scores, dict) and operation:
        detail["operation"] = _round_log_score(operation_scores.get(operation, 0.0))
    if isinstance(domain_scores, dict):
        detail["domain"] = {
            key: _round_log_score(value) for key, value in domain_scores.items()
        }
    if isinstance(matched, list):
        for item in matched:
            if not isinstance(item, dict):
                continue
            if item.get("capability") == capability and (
                not operation or item.get("operation") == operation
            ):
                detail["candidate_score"] = _round_log_score(item.get("score", 0.0))
                break
    return detail


def _why_selected(
    decision: RouterDecision,
    route: str,
    capability: str,
    operation: object,
) -> str:
    path = selection_path(decision)
    if path == "hybrid_retrieval":
        return f"混合召回候选 {route} 进入预算后被 policy 选中"
    if path == "write_candidate_retriever":
        return f"写意图召回候选 {route}，需要确认后执行"
    if path.startswith("fallback:"):
        return decision.fallback_reason or "fallback policy selected"
    if operation:
        return f"规则分类器命中 {capability}.{operation}"
    return f"规则分类器命中 {capability}"


def _decision_recall_summary(
    decision: RouterDecision,
    *,
    vector_index_enabled: bool,
) -> dict:
    hybrid_recall = _hybrid_recall(decision)
    if hybrid_recall is not None:
        return hybrid_recall

    path = selection_path(decision)
    if path == "rule_classifier":
        return _non_vector_recall_summary(
            path="rule_classifier",
            retrieval_engine="rule_intent_classifier",
            scoring_kind="rule_scores",
            skip_reason="rule_classifier_matched",
            decision=decision,
            vector_index_enabled=vector_index_enabled,
        )
    if path == "write_candidate_retriever":
        return _non_vector_recall_summary(
            path="write_candidate_retriever",
            retrieval_engine="metadata_candidate_retriever",
            scoring_kind="metadata_keyword_scores",
            skip_reason="write_candidate_retriever",
            decision=decision,
            vector_index_enabled=vector_index_enabled,
        )
    return _non_vector_recall_summary(
        path=path,
        retrieval_engine="none",
        scoring_kind="policy_scores",
        skip_reason=decision.fallback_reason or "not_retrieval_path",
        decision=decision,
        vector_index_enabled=vector_index_enabled,
    )


def _hybrid_recall(decision: RouterDecision) -> dict | None:
    for frame in decision.frames:
        recall = frame.evidence.get("recall")
        if not isinstance(recall, dict):
            continue
        summary = dict(recall)
        top_candidates = frame.evidence.get("top_candidates")
        if isinstance(top_candidates, list):
            summary["top_candidates"] = top_candidates
        summary["selected_routes"] = _selected_routes(decision)
        return summary
    return None


def _non_vector_recall_summary(
    *,
    path: str,
    retrieval_engine: str,
    scoring_kind: str,
    skip_reason: str,
    decision: RouterDecision,
    vector_index_enabled: bool,
) -> dict:
    selected_routes = _selected_routes(decision)
    return {
        "path": path,
        "retrieval_engine": retrieval_engine,
        "scoring_kind": scoring_kind,
        "candidate_count": len(selected_routes),
        "selected_routes": selected_routes,
        "bm25_used": False,
        "vector_index_enabled": vector_index_enabled,
        "vector_search_used": False,
        "rag_service_used": False,
        "quillrag_retrieve_used": False,
        "external_embedding_requested": False,
        "embedding_location": "none",
        "local_embedding_used": False,
        "local_query_embedding_calls": 0,
        "local_doc_embedding_calls": 0,
        "skip_reason": skip_reason,
    }


def _selected_routes(decision: RouterDecision) -> list[str]:
    selected = decision.evidence.get("selected_candidates")
    if isinstance(selected, list):
        routes = [
            _candidate_route(item)
            for item in selected
            if isinstance(item, dict) and _candidate_route(item)
        ]
        if routes:
            return routes
    routes: list[str] = []
    for tool_name in decision.selected_tools:
        operations = []
        for values in decision.selected_operations.values():
            operations.extend(values)
        if operations:
            routes.extend(f"{tool_name}.{operation}" for operation in operations)
        else:
            routes.append(tool_name)
    return routes


def _round_log_score(value: object) -> float:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return 0.0

