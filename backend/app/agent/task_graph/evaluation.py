"""Task Graph 离线评测报告辅助。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal

from app.agent.task_graph.models import EvaluationReport, TaskType

AggregateKey = Literal["planner_version", "task_type", "capability", "request_id"]


def create_evaluation_report(
    *,
    evaluation_id: str,
    request_id: str,
    task_type: TaskType,
    planner_version: str,
    slot_score: float,
    plan_ir_valid: bool,
    graph_compile_success: bool,
    contract_pass_rate: float,
    capability_success_rate: float,
    repair_count: int,
    retry_count: int,
    hallucination_count: int,
    latency_ms: int,
    token_count: int,
    capability_metrics: dict[str, dict[str, Any]] | None = None,
) -> EvaluationReport:
    return EvaluationReport(
        evaluation_id=evaluation_id,
        request_id=request_id,
        task_type=task_type,
        planner_version=planner_version,
        slot_score=slot_score,
        plan_ir_valid=plan_ir_valid,
        graph_compile_success=graph_compile_success,
        contract_pass_rate=contract_pass_rate,
        capability_success_rate=capability_success_rate,
        repair_count=repair_count,
        retry_count=retry_count,
        hallucination_count=hallucination_count,
        latency_ms=latency_ms,
        token_count=token_count,
        capability_metrics=capability_metrics or {},
    )


def aggregate_reports(
    reports: list[EvaluationReport], *, by: AggregateKey
) -> dict[str, dict[str, float | int]]:
    if by == "capability":
        return _aggregate_by_capability(reports)

    grouped: dict[str, list[EvaluationReport]] = defaultdict(list)
    for report in reports:
        grouped[str(getattr(report, by))].append(report)

    return {key: _summarize_reports(items) for key, items in grouped.items()}


def _aggregate_by_capability(
    reports: list[EvaluationReport],
) -> dict[str, dict[str, float | int]]:
    grouped: dict[str, list[bool]] = defaultdict(list)
    for report in reports:
        for capability, metrics in report.capability_metrics.items():
            grouped[capability].append(bool(metrics.get("success")))
    return {
        capability: {
            "count": len(values),
            "success_rate": _round(sum(1 for value in values if value) / len(values)),
        }
        for capability, values in grouped.items()
        if values
    }


def _summarize_reports(reports: list[EvaluationReport]) -> dict[str, float | int]:
    count = len(reports)
    return {
        "count": count,
        "slot_score_avg": _avg(report.slot_score for report in reports),
        "plan_ir_valid_rate": _avg(
            1.0 if report.plan_ir_valid else 0.0 for report in reports
        ),
        "graph_compile_success_rate": _avg(
            1.0 if report.graph_compile_success else 0.0 for report in reports
        ),
        "contract_pass_rate_avg": _avg(report.contract_pass_rate for report in reports),
        "capability_success_rate_avg": _avg(
            report.capability_success_rate for report in reports
        ),
        "repair_count_sum": sum(report.repair_count for report in reports),
        "retry_count_sum": sum(report.retry_count for report in reports),
        "hallucination_count_sum": sum(
            report.hallucination_count for report in reports
        ),
        "latency_ms_avg": _avg(report.latency_ms for report in reports),
        "token_count_avg": _avg(report.token_count for report in reports),
    }


def _avg(values: Any) -> float:
    items = list(values)
    if not items:
        return 0.0
    return _round(sum(items) / len(items))


def _round(value: float) -> float:
    return round(value, 4)
