"""Skill Router trace 诊断证据构建。"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agent.router.models import RouterDecision

_SCHEMA_VERSION = 2


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


def skill_router_trace_payload(
    decision: RouterDecision,
    *,
    plan_draft_payload: dict | None = None,
    candidate_count: int | None = None,
    debug_raw: dict | None = None,
) -> dict:
    """构造默认落库的 Skill Router trace JSON。"""

    recall = decision.evidence.get("recall")
    if not isinstance(recall, dict):
        recall = _decision_recall_summary(decision, vector_index_enabled=False)
    explanations = decision.evidence.get("candidate_explanations")
    if not isinstance(explanations, list):
        explanations = candidate_explanations(decision)
    selected_routes = _selected_routes(decision)
    payload: dict = {
        "schema_version": _SCHEMA_VERSION,
        "summary": {
            "selection_path": selection_path(decision),
            "selection_reason": decision.reason,
            "selected_routes": selected_routes,
            "candidate_count": _candidate_count(decision, candidate_count),
            "fallback": decision.fallback,
            "fallback_reason": decision.fallback_reason,
            "policy_violations": list(decision.policy_violations),
        },
        "selected": {
            "tools": list(decision.selected_tools),
            "operations": dict(decision.selected_operations),
            "tool_choice": decision.tool_choice,
            "force_binding": list(decision.force_binding),
        },
        "recall": _compact_recall(recall),
        "candidate_explanations": explanations,
        "plan": _compact_plan(plan_draft_payload),
    }
    if debug_raw is not None:
        payload["debug_raw"] = debug_raw
    return _drop_empty(payload)


def format_skill_router_trace(
    decision: RouterDecision,
    *,
    candidate_count: int,
    duration_ms: int,
    max_candidates: int = 8,
) -> str:
    """返回适合终端阅读的 Skill Router trace 摘要。"""

    recall = decision.evidence.get("recall")
    if not isinstance(recall, dict):
        recall = _decision_recall_summary(decision, vector_index_enabled=False)
    explanations = decision.evidence.get("candidate_explanations")
    if not isinstance(explanations, list):
        explanations = candidate_explanations(decision)
    selected_routes = _selected_routes(decision)
    lines = [
        "Skill Router Trace",
        (
            "  route: "
            f"path={recall.get('path') or selection_path(decision)} "
            f"engine={recall.get('retrieval_engine') or 'unknown'} "
            f"duration_ms={duration_ms} "
            f"candidates={candidate_count}"
        ),
    ]
    lines.extend(_format_recall_lines(recall))
    lines.append(
        "  selected: "
        f"routes={_format_list(selected_routes)} "
        f"tools={_format_list(decision.selected_tools)}"
    )
    if decision.selected_operations:
        lines.append(f"  operations: {_format_operations(decision.selected_operations)}")
    if decision.fallback or decision.fallback_reason:
        lines.append(
            "  fallback: "
            f"{decision.fallback or '-'} reason={decision.fallback_reason or '-'}"
        )
    if decision.policy_violations:
        lines.append(f"  policy_violations: {_format_list(decision.policy_violations)}")
    lines.append("  candidate_scores:")
    lines.extend(_format_candidate_lines(explanations[:max_candidates], selected_routes))
    if len(explanations) > max_candidates:
        lines.append(f"    ... {len(explanations) - max_candidates} more")
    return "\n".join(lines)


def _candidate_count(decision: RouterDecision, candidate_count: int | None) -> int:
    if candidate_count is not None:
        return candidate_count
    candidates = decision.evidence.get("selected_candidates")
    if isinstance(candidates, list):
        return len(candidates)
    explanations = decision.evidence.get("candidate_explanations")
    if isinstance(explanations, list):
        return len(explanations)
    return len(decision.selected_tools)


def _compact_recall(recall: dict) -> dict:
    payload = dict(recall)
    status = str(payload.get("status") or "")
    if not status:
        status = "used" if payload.get("vector_search_used") else "skipped"
    payload["status"] = status
    payload.setdefault("path", payload.get("selection_path") or "unknown")
    if status == "skipped" and payload.get("skip_reason"):
        payload.setdefault("meaning", _recall_skip_meaning(payload))
    elif status == "used":
        payload.setdefault(
            "meaning",
            "规则分类器未给出稳定候选，使用 BM25 + QuillRAG 向量混合召回",
        )
    return _drop_empty(payload)


def _compact_plan(plan_draft_payload: dict | None) -> dict:
    if not isinstance(plan_draft_payload, dict):
        return {}
    return _drop_empty(
        {
            "route_type": plan_draft_payload.get("route_type"),
            "steps": [
                _compact_plan_step(step)
                for step in plan_draft_payload.get("steps", [])
                if isinstance(step, dict)
            ],
            "validation": _compact_validation(plan_draft_payload.get("validation")),
        }
    )


def _compact_plan_step(step: dict) -> dict:
    params = step.get("params")
    operation = step.get("operation")
    if operation in (None, "") and isinstance(params, dict):
        operation = params.get("operation")
    return _drop_empty(
        {
            "step_id": step.get("step_id"),
            "skill_name": step.get("skill_name"),
            "operation": operation,
            "risk": step.get("risk"),
            "depends_on": step.get("depends_on"),
        }
    )


def _compact_validation(validation: object) -> dict:
    if not isinstance(validation, dict):
        return {}
    return _drop_empty(
        {
            "status": validation.get("status"),
            "issues": validation.get("issues"),
            "missing_fields": validation.get("missing_fields"),
            "inferred_fields": validation.get("inferred_fields"),
        }
    )


def _drop_empty(value):
    if isinstance(value, dict):
        compact = {}
        for key, nested in value.items():
            cleaned = _drop_empty(nested)
            if cleaned in (None, "", [], {}):
                continue
            compact[key] = cleaned
        return compact
    if isinstance(value, list):
        compact = []
        for item in value:
            cleaned = _drop_empty(item)
            if cleaned not in ({}, []):
                compact.append(cleaned)
        return compact
    return value


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
        operations = list(decision.selected_operations.get(tool_name) or [])
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


def _format_recall_lines(recall: dict) -> list[str]:
    used = bool(recall.get("bm25_used") or recall.get("vector_search_used"))
    if not used:
        return [
            "  recall: skipped",
            f"    reason: {recall.get('skip_reason') or 'not_retrieval_path'}",
            f"    meaning: {_recall_skip_meaning(recall)}",
            f"    external_rag_call: {_bool_label(recall.get('rag_service_used'))}",
            f"    embedding_call: {_bool_label(recall.get('external_embedding_requested'))}",
            f"    local_doc_embeds: {recall.get('local_doc_embedding_calls', 0)}",
        ]
    return [
        "  recall: used",
        f"    strategy: {_recall_strategy(recall)}",
        f"    external_rag_call: {_bool_label(recall.get('rag_service_used'))}",
        f"    quillrag_call: {_bool_label(recall.get('quillrag_retrieve_used'))}",
        f"    embedding_location: {recall.get('embedding_location') or 'none'}",
        f"    local_doc_embeds: {recall.get('local_doc_embedding_calls', 0)}",
        f"    vector_status: {recall.get('vector_status') or '-'}",
    ]


def _recall_skip_meaning(recall: dict) -> str:
    reason = str(recall.get("skip_reason") or "")
    if reason == "rule_classifier_matched":
        return "规则分类器已命中，跳过 BM25 + RAG 向量召回"
    if reason == "not_retrievable_read":
        return "输入不像可检索读问题，未触发 Skill 混合召回"
    if reason == "write_candidate_retriever":
        return "写意图走元数据候选召回，未触发读场景向量召回"
    if reason == "unresolved_write":
        return "写意图未解析出可执行候选，未触发读场景向量召回"
    return "本次路由没有进入 BM25 + RAG 向量召回路径"


def _recall_strategy(recall: dict) -> str:
    parts: list[str] = []
    if recall.get("bm25_used"):
        parts.append("bm25")
    if recall.get("quillrag_retrieve_used"):
        parts.append("quillrag_vector")
    elif recall.get("vector_search_used"):
        parts.append("vector")
    return " + ".join(parts) if parts else "none"


def _format_candidate_lines(
    explanations: list[object],
    selected_routes: list[str],
) -> list[str]:
    if not explanations:
        return ["    - none"]
    lines: list[str] = []
    selected_set = set(selected_routes)
    for index, item in enumerate(explanations, start=1):
        if not isinstance(item, dict):
            continue
        route = str(item.get("route") or "-")
        selected = bool(item.get("selected")) or route in selected_set
        scores = item.get("scores") if isinstance(item.get("scores"), dict) else {}
        lines.append(
            "    "
            f"{index}. {_selection_mark(selected)} {route} "
            f"final={_score_value(scores, 'final', 'score')} "
            f"bm25={_score_value(scores, 'bm25')} "
            f"vector={_score_value(scores, 'vector')} "
            f"lexical={_score_value(scores, 'lexical')} "
            f"capability={_score_value(scores, 'capability')} "
            f"operation={_score_value(scores, 'operation')} "
            f"sources={_format_list(scores.get('sources') or [])}"
        )
        why_selected = item.get("why_selected")
        if why_selected:
            lines.append(f"       why: {why_selected}")
        hits = _format_hits(scores)
        if hits:
            lines.append(f"       hits: {hits}")
    return lines or ["    - none"]


def _score_value(scores: dict, *keys: str) -> str:
    for key in keys:
        if key in scores:
            return f"{_round_log_score(scores.get(key)):.4f}"
    return "-"


def _format_hits(scores: dict) -> str:
    parts = []
    for key in ("lexical_hits", "low_signal_hits", "anti_hits"):
        values = scores.get(key)
        if values:
            parts.append(f"{key}={_format_list(values)}")
    return " ".join(parts)


def _selection_mark(selected: bool) -> str:
    return "[selected]" if selected else "[candidate]"


def _bool_label(value: object) -> str:
    return "yes" if bool(value) else "no"


def _format_list(values: object) -> str:
    if not isinstance(values, list | tuple | set):
        return str(values) if values else "-"
    return ",".join(str(value) for value in values) if values else "-"


def _format_operations(operations: dict[str, list[str]]) -> str:
    parts = []
    for skill, values in operations.items():
        parts.append(f"{skill}={_format_list(values)}")
    return "; ".join(parts) if parts else "-"
