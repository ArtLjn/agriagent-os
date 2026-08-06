"""业务路由召回评测工具。"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml
from langchain_core.tools import BaseTool

from app.agent.router import classifier_signals as signals
from app.agent.router.catalog import SkillCatalog
from app.agent.router.hybrid_retriever import HybridOperationRetriever
from app.agent.router.intent import IntentType, classify_intent
from app.agent.router.models import RouterDecision, ToolCandidate
from app.agent.router.service import SkillRouter
from app.agent.router.skill_vector_store import build_skill_vector_search_fn
from app.infra.trace_diagnostics import selection_path
from app.skills.registry import OperationDefinition, load_skill_registry


DEFAULT_ROUTE_CASES_PATH = Path(__file__).with_name("skill_route_cases.json")
_READ_OPERATION_RISKS = frozenset({"read", "external_network"})
_WRITE_OPERATION_RISKS = frozenset({"write_confirm", "write_high"})


@dataclass(frozen=True)
class ExpectedRoute:
    skill: str
    operation: str | None = None


@dataclass(frozen=True)
class RouteRecallCase:
    id: str
    message: str
    expected: ExpectedRoute
    acceptable: tuple[ExpectedRoute, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RouteRecallFailure:
    case_id: str
    message: str
    expected: ExpectedRoute
    top_k: list[ExpectedRoute]
    scores: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteRecallCandidate:
    skill: str
    operation: str | None
    score: float
    risk: str
    operation_risk: str | None
    evidence: dict[str, Any]


@dataclass(frozen=True)
class RouteRecallPreview:
    candidates: list[RouteRecallCandidate]
    vector_index_enabled: bool
    recall_mode: str
    recall: dict[str, Any]
    top_candidates: list[dict[str, Any]]


@dataclass(frozen=True)
class RouteRecallReport:
    total: int
    recall_at_1: float
    recall_at_k: float
    operation_recall_at_k: float
    failures: list[RouteRecallFailure]


@dataclass(frozen=True)
class RouterRouteFailure:
    case_id: str
    message: str
    expected: ExpectedRoute
    selected: list[ExpectedRoute]
    selected_tools: list[str]
    selected_operations: dict[str, list[str]]
    selection_path: str
    reason: str


@dataclass(frozen=True)
class RouterRouteReport:
    total: int
    route_accuracy: float
    exact_match_rate: float
    failures: list[RouterRouteFailure]
    strict_failures: list[RouterRouteFailure]


def load_route_cases(path: Path) -> list[RouteRecallCase]:
    """读取业务路由评测样本。"""
    raw = _load_case_payload(path)
    return [_route_case_from_dict(item) for item in raw]


def preview_route_recall(
    message: str,
    tools: list[BaseTool],
    *,
    top_k: int = 5,
    retriever: HybridOperationRetriever | None = None,
) -> list[RouteRecallCandidate]:
    """预览单条业务输入的 Skill 候选召回结果。"""
    return preview_route_recall_detail(
        message,
        tools,
        top_k=top_k,
        retriever=retriever,
    ).candidates


def preview_route_recall_detail(
    message: str,
    tools: list[BaseTool],
    *,
    top_k: int = 5,
    retriever: HybridOperationRetriever | None = None,
) -> RouteRecallPreview:
    """预览单条业务输入的 Skill 候选召回详情。"""
    candidate_scope = _candidate_scope_for_message(message)
    candidates = _operation_candidates_for_scope(candidate_scope, tools)
    route_retriever = retriever or _default_hybrid_retriever()
    result = route_retriever.retrieve(
        message,
        candidates,
        limit=len(candidates),
        candidate_scope=candidate_scope,
    )
    return RouteRecallPreview(
        candidates=_top_unique_skill_candidates(
            result.selected_candidates,
            result.scores,
            result.evidence,
            top_k,
        ),
        vector_index_enabled=route_retriever.vector_index_enabled,
        recall_mode="hybrid_vector"
        if route_retriever.vector_index_enabled
        else "hybrid_local",
        recall=result.recall,
        top_candidates=result.top_candidates,
    )


def evaluate_route_recall(
    cases: list[RouteRecallCase],
    tools: list[BaseTool],
    *,
    top_k: int = 5,
    retriever: HybridOperationRetriever | None = None,
) -> RouteRecallReport:
    """评测 operation 级召回命中率。"""
    route_retriever = retriever or _default_hybrid_retriever()
    failures: list[RouteRecallFailure] = []
    hit_1 = 0
    hit_k = 0
    operation_hit_k = 0

    for case in cases:
        candidate_scope = _candidate_scope_for_message(case.message)
        candidates = _operation_candidates_for_scope(candidate_scope, tools)
        result = route_retriever.retrieve(
            case.message,
            candidates,
            limit=len(candidates),
            candidate_scope=candidate_scope,
        )
        routes = _top_unique_skill_routes(result.selected_candidates, top_k)
        accepted = _accepted_routes(case)
        if routes and _skill_hit(routes[0], accepted):
            hit_1 += 1
        if any(_skill_hit(route, accepted) for route in routes):
            hit_k += 1
        if any(route in accepted for route in routes):
            operation_hit_k += 1
        else:
            failures.append(
                RouteRecallFailure(
                    case_id=case.id,
                    message=case.message,
                    expected=case.expected,
                    top_k=routes,
                    scores=result.scores,
                )
            )

    total = len(cases)
    return RouteRecallReport(
        total=total,
        recall_at_1=_ratio(hit_1, total),
        recall_at_k=_ratio(hit_k, total),
        operation_recall_at_k=_ratio(operation_hit_k, total),
        failures=failures,
    )


def evaluate_router_routes(
    cases: list[RouteRecallCase],
    tools: list[BaseTool],
    *,
    router: SkillRouter | None = None,
) -> RouterRouteReport:
    """评测 SkillRouter 最终 selected_tools/selected_operations 是否命中样本。"""
    route_router = router or SkillRouter()
    failures: list[RouterRouteFailure] = []
    strict_failures: list[RouterRouteFailure] = []
    hit = 0
    exact_hit = 0

    for case in cases:
        decision = route_router.route(case.message, tools)
        selected = _decision_routes(decision.selected_operations)
        accepted = _accepted_routes(case)
        route_hit = any(route in accepted for route in selected)
        exact_route_hit = _exact_route_match(selected, accepted)
        if route_hit:
            hit += 1
        else:
            failures.append(_router_route_failure(case, decision, selected))
        if exact_route_hit:
            exact_hit += 1
        else:
            strict_failures.append(_router_route_failure(case, decision, selected))

    total = len(cases)
    return RouterRouteReport(
        total=total,
        route_accuracy=_ratio(hit, total),
        exact_match_rate=_ratio(exact_hit, total),
        failures=failures,
        strict_failures=strict_failures,
    )


def format_report(report: RouteRecallReport, *, top_k: int) -> str:
    """格式化 CLI 评测报告。"""
    lines = [
        f"cases: {report.total}",
        f"recall@1: {report.recall_at_1:.1%}",
        f"recall@{top_k}: {report.recall_at_k:.1%}",
        f"operation_hit@{top_k}: {report.operation_recall_at_k:.1%}",
    ]
    if not report.failures:
        lines.append("失败样本: 0")
        return "\n".join(lines)
    lines.append("")
    lines.append("失败样本:")
    for failure in report.failures:
        expected = _route_label(failure.expected)
        top = ", ".join(_route_label(route) for route in failure.top_k) or "-"
        lines.append(f"- {failure.case_id}: {failure.message}")
        lines.append(f"  expected: {expected}")
        lines.append(f"  top{top_k}: {top}")
    return "\n".join(lines)


def _default_hybrid_retriever() -> HybridOperationRetriever:
    """评测/预览入口默认接入 QuillRAG 向量召回。"""
    return HybridOperationRetriever(vector_search=build_skill_vector_search_fn())


def default_route_cases_path() -> Path:
    """返回 Admin UI 使用的默认 JSON 召回测试集路径。"""
    return DEFAULT_ROUTE_CASES_PATH


def active_eval_tools() -> list[BaseTool]:
    """构建与 CLI/Admin 评测一致的 active Skill 工具列表。"""
    return [_EvalTool(name) for name in _active_skill_names()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="评测业务 Skill 路由召回率。")
    parser.add_argument("cases", type=Path, help="业务路由样本 YAML 文件。")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args(argv)

    cases = load_route_cases(args.cases)
    tools = [_EvalTool(name) for name in _active_skill_names()]
    report = evaluate_route_recall(cases, tools, top_k=args.top_k)
    print(format_report(report, top_k=args.top_k))
    return 0 if not report.failures else 1


def _load_case_payload(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8") or "[]")
    else:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(payload, list):
        raise ValueError("业务路由评测样本顶层必须是 list")
    return [dict(item) for item in payload]


def _route_case_from_dict(item: dict[str, Any]) -> RouteRecallCase:
    return RouteRecallCase(
        id=str(item["id"]),
        message=str(item["message"]),
        expected=_expected_route(item["expected"]),
        acceptable=tuple(
            _expected_route(value) for value in item.get("acceptable", [])
        ),
        tags=tuple(str(tag) for tag in item.get("tags", [])),
    )


def _expected_route(value: dict[str, Any]) -> ExpectedRoute:
    return ExpectedRoute(
        skill=str(value["skill"]),
        operation=str(value["operation"]) if value.get("operation") else None,
    )


def _operation_candidates_for_scope(
    candidate_scope: str,
    tools: list[BaseTool],
) -> list[ToolCandidate]:
    if candidate_scope == "write":
        return _operation_candidates(tools, risks=_WRITE_OPERATION_RISKS)
    return _operation_candidates(tools, risks=_READ_OPERATION_RISKS)


def _candidate_scope_for_message(message: str) -> str:
    return "write" if _looks_like_write_message(message) else "read"


def _operation_candidates(
    tools: list[BaseTool],
    *,
    risks: frozenset[str] | None = None,
) -> list[ToolCandidate]:
    catalog = SkillCatalog.from_tools(tools)
    candidates: list[ToolCandidate] = []
    for candidate in catalog.candidates():
        candidates.extend(_expand_candidate_operations(candidate, risks=risks))
    return candidates


def _expand_candidate_operations(
    candidate: ToolCandidate,
    *,
    risks: frozenset[str] | None = None,
) -> list[ToolCandidate]:
    if candidate.capability is None:
        return [candidate] if _candidate_matches_risk(candidate, risks) else []
    try:
        registry = load_skill_registry()
    except (OSError, ValueError):
        return [candidate] if _candidate_matches_risk(candidate, risks) else []
    capability = registry.capabilities.get(candidate.capability)
    if capability is None:
        return [candidate] if _candidate_matches_risk(candidate, risks) else []
    expanded = [
        _candidate_for_operation(candidate, operation)
        for operation in capability.operations.values()
        if risks is None or operation.risk in risks
    ]
    if expanded:
        return expanded
    return [candidate] if _candidate_matches_risk(candidate, risks) else []


def _candidate_for_operation(
    candidate: ToolCandidate,
    operation: OperationDefinition,
) -> ToolCandidate:
    return replace(
        candidate,
        operation=operation.name,
        operation_risk=operation.risk,
        risk="read"
        if operation.risk in {"read", "external_network"}
        else operation.risk,
        intents=[
            operation.name,
            candidate.capability or "",
            candidate.name,
            *list(operation.legacy_aliases),
        ],
        trigger_examples=[
            *candidate.trigger_examples,
            operation.description,
        ],
        legacy_alias=operation.legacy_aliases[0]
        if operation.legacy_aliases
        else candidate.legacy_alias,
        candidate_group=f"{candidate.domain}_{operation.risk}",
        evidence={
            **candidate.evidence,
            "operation": operation.name,
            "operation_risk": operation.risk,
        },
    )


def _candidate_matches_risk(
    candidate: ToolCandidate,
    risks: frozenset[str] | None,
) -> bool:
    if risks is None:
        return True
    risk = candidate.operation_risk or candidate.risk
    return risk in risks


def _looks_like_write_message(message: str) -> bool:
    if (
        signals.looks_like_daily_operation_advice(message)
        or signals.looks_like_weather_crop_impact_query(message)
        or signals.looks_like_weather_query(message)
    ):
        return False
    if classify_intent(message) == IntentType.WRITE:
        return True
    return (
        signals.looks_like_create_work_order(message)
        or signals.looks_like_create_worker(message)
        or signals.looks_like_manage_wage(message)
        or signals.looks_like_create_cost_record(message)
        or signals.looks_like_create_crop_cycle(message)
        or signals.looks_like_manage_planting_unit(message)
        or signals.looks_like_create_crop_template(message)
        or signals.looks_like_manage_cost_category(message)
    )


def _accepted_routes(case: RouteRecallCase) -> set[ExpectedRoute]:
    return {case.expected, *case.acceptable}


def _decision_routes(selected_operations: dict[str, list[str]]) -> list[ExpectedRoute]:
    routes: list[ExpectedRoute] = []
    for skill, operations in selected_operations.items():
        if not operations:
            routes.append(ExpectedRoute(skill=skill))
            continue
        routes.extend(
            ExpectedRoute(skill=skill, operation=operation) for operation in operations
        )
    return routes


def _exact_route_match(
    selected: list[ExpectedRoute],
    accepted: set[ExpectedRoute],
) -> bool:
    return len(selected) == 1 and bool(selected) and selected[0] in accepted


def _router_route_failure(
    case: RouteRecallCase,
    decision: RouterDecision,
    selected: list[ExpectedRoute],
) -> RouterRouteFailure:
    return RouterRouteFailure(
        case_id=case.id,
        message=case.message,
        expected=case.expected,
        selected=selected,
        selected_tools=list(decision.selected_tools),
        selected_operations=dict(decision.selected_operations),
        selection_path=selection_path(decision),
        reason=decision.reason,
    )


def _route_from_candidate(candidate: ToolCandidate) -> ExpectedRoute:
    return ExpectedRoute(skill=candidate.name, operation=candidate.operation)


def _top_unique_skill_routes(
    candidates: list[ToolCandidate],
    top_k: int,
) -> list[ExpectedRoute]:
    routes: list[ExpectedRoute] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.name in seen:
            continue
        seen.add(candidate.name)
        routes.append(_route_from_candidate(candidate))
        if len(routes) >= top_k:
            break
    return routes


def _top_unique_skill_candidates(
    candidates: list[ToolCandidate],
    scores: dict[str, float],
    evidence: dict[str, dict],
    top_k: int,
) -> list[RouteRecallCandidate]:
    items: list[RouteRecallCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.name in seen:
            continue
        seen.add(candidate.name)
        route_key = _candidate_route_key(candidate)
        candidate_evidence = evidence.get(route_key, evidence.get(candidate.name, {}))
        score = candidate_evidence.get(
            "score",
            scores.get(route_key, scores.get(candidate.name, 0.0)),
        )
        items.append(
            RouteRecallCandidate(
                skill=candidate.name,
                operation=candidate.operation,
                score=float(score),
                risk=candidate.risk,
                operation_risk=candidate.operation_risk,
                evidence=candidate_evidence,
            )
        )
        if len(items) >= top_k:
            break
    return items


def _candidate_route_key(candidate: ToolCandidate) -> str:
    if candidate.operation:
        return f"{candidate.name}.{candidate.operation}"
    return candidate.name


def _skill_hit(route: ExpectedRoute, accepted: set[ExpectedRoute]) -> bool:
    return any(route.skill == item.skill for item in accepted)


def _route_label(route: ExpectedRoute) -> str:
    if route.operation:
        return f"{route.skill}.{route.operation}"
    return route.skill


def _ratio(value: int, total: int) -> float:
    return value / total if total else 0.0


def _active_skill_names() -> list[str]:
    registry = load_skill_registry()
    return [
        capability.name
        for capability in registry.capabilities.values()
        if capability.status == "active"
    ]


class _EvalTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = name


if __name__ == "__main__":
    raise SystemExit(main())
