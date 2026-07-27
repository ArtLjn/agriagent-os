"""业务路由召回评测工具。"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import yaml
from langchain_core.tools import BaseTool

from app.agent.router.candidate_retriever import CandidateRetriever
from app.agent.router.catalog import SkillCatalog
from app.agent.router.models import ToolCandidate
from app.skills.registry import OperationDefinition, load_skill_registry


DEFAULT_ROUTE_CASES_PATH = Path(__file__).with_name("skill_route_cases.json")


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
class RouteRecallReport:
    total: int
    recall_at_1: float
    recall_at_k: float
    operation_recall_at_k: float
    failures: list[RouteRecallFailure]


def load_route_cases(path: Path) -> list[RouteRecallCase]:
    """读取业务路由评测样本。"""
    raw = _load_case_payload(path)
    return [_route_case_from_dict(item) for item in raw]


def preview_route_recall(
    message: str,
    tools: list[BaseTool],
    *,
    top_k: int = 5,
) -> list[RouteRecallCandidate]:
    """预览单条业务输入的 Skill 候选召回结果。"""
    candidates = _operation_candidates(tools)
    result = CandidateRetriever().retrieve(message, candidates, limit=len(candidates))
    return _top_unique_skill_candidates(
        result.selected_candidates,
        result.scores,
        result.evidence,
        top_k,
    )


def evaluate_route_recall(
    cases: list[RouteRecallCase],
    tools: list[BaseTool],
    *,
    top_k: int = 5,
) -> RouteRecallReport:
    """评测 operation 级召回命中率。"""
    candidates = _operation_candidates(tools)
    retriever = CandidateRetriever()
    failures: list[RouteRecallFailure] = []
    hit_1 = 0
    hit_k = 0
    operation_hit_k = 0

    for case in cases:
        result = retriever.retrieve(case.message, candidates, limit=len(candidates))
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


def _operation_candidates(tools: list[BaseTool]) -> list[ToolCandidate]:
    catalog = SkillCatalog.from_tools(tools)
    candidates: list[ToolCandidate] = []
    for candidate in catalog.candidates():
        candidates.extend(_expand_candidate_operations(candidate))
    return candidates


def _expand_candidate_operations(candidate: ToolCandidate) -> list[ToolCandidate]:
    if candidate.capability is None:
        return [candidate]
    try:
        registry = load_skill_registry()
    except (OSError, ValueError):
        return [candidate]
    capability = registry.capabilities.get(candidate.capability)
    if capability is None:
        return [candidate]
    expanded = [
        _candidate_for_operation(candidate, operation)
        for operation in capability.operations.values()
    ]
    return expanded or [candidate]


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


def _accepted_routes(case: RouteRecallCase) -> set[ExpectedRoute]:
    return {case.expected, *case.acceptable}


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
        candidate_evidence = evidence.get(candidate.name, {})
        score = candidate_evidence.get("score", scores.get(candidate.name, 0.0))
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
