"""每日建议 v2 校验规则实现。"""

from __future__ import annotations

from typing import Any

from app.domains.conversation.daily_advice_models import DailyAdviceCandidate
from app.domains.conversation.daily_advice_validation_models import (
    FORBIDDEN_DAILY_ADVICE_TERMS,
    DailyAdviceValidationIssue,
)
from app.domains.conversation.daily_advice_validation_text import collect_text_bounds_reasons

_CONTENT_TOO_THIN = "daily_advice_content_too_thin"
_EMPTY_MODES = {"empty", "fallback"}
_REQUIRED_TOP_LEVEL_FIELDS = (
    "preview",
    "overview",
    "items",
    "generation",
    "created_at",
)
_REQUIRED_OVERVIEW_METRIC_KEYS = {"weather", "work_order", "pending"}


def validate_candidate_identity(
    *,
    item: dict[str, Any],
    item_path: str,
    candidate_by_id: dict[str, DailyAdviceCandidate],
    issues: list[DailyAdviceValidationIssue],
) -> DailyAdviceCandidate | None:
    item_id = item.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        issues.append(
            DailyAdviceValidationIssue(
                code="candidate_id_not_allowed",
                message="每日建议 item.id 必须命中 selected candidates。",
                path=f"{item_path}.id",
                evidence={
                    "item_id": item_id,
                    "allowed_ids": sorted(candidate_by_id),
                },
            )
        )
        return None

    candidate = candidate_by_id.get(item_id)
    if candidate is None:
        issues.append(
            DailyAdviceValidationIssue(
                code="candidate_id_not_allowed",
                message="每日建议 item.id 不在 selected candidates 中。",
                path=f"{item_path}.id",
                evidence={
                    "item_id": item_id,
                    "allowed_ids": sorted(candidate_by_id),
                },
            )
        )
    return candidate


def validate_content_completeness(
    item: dict[str, Any],
    item_path: str,
    mode: str,
    issues: list[DailyAdviceValidationIssue],
) -> None:
    compact = item.get("compact")
    detail_view = item.get("detail_view")
    thin_reasons: list[dict[str, Any]] = []

    if not isinstance(compact, dict):
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="每日建议 item.compact 必须是 dict。",
                path=f"{item_path}.compact",
                evidence={"actual_type": type(compact).__name__},
            )
        )
        compact = {}

    if not isinstance(detail_view, dict):
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="每日建议 item.detail_view 必须是 dict。",
                path=f"{item_path}.detail_view",
                evidence={"actual_type": type(detail_view).__name__},
            )
        )
        detail_view = {}

    _collect_text_thin_reasons(compact, detail_view, item_path, thin_reasons)
    _collect_steps_thin_reasons(detail_view, item_path, thin_reasons)
    _collect_actions_thin_reasons(detail_view, item_path, thin_reasons)
    _collect_evidence_thin_reasons(detail_view, item_path, mode, thin_reasons)

    if thin_reasons:
        issues.append(
            DailyAdviceValidationIssue(
                code=_CONTENT_TOO_THIN,
                message="每日建议内容不完整或过短。",
                path=item_path,
                evidence={"reasons": thin_reasons},
            )
        )


def validate_candidate_fields(
    item: dict[str, Any],
    item_path: str,
    candidate: DailyAdviceCandidate,
    issues: list[DailyAdviceValidationIssue],
) -> None:
    priority = item.get("priority")
    priority_issue = _priority_issue(priority, item_path, candidate)
    if priority_issue is not None:
        issues.append(priority_issue)

    if isinstance(priority, int) and 1 <= priority <= 3 and priority < candidate.priority:
        issues.append(
            DailyAdviceValidationIssue(
                code="priority_escalation_not_allowed",
                message="每日建议 priority 不能高于候选优先级。",
                path=f"{item_path}.priority",
                evidence={
                    "item_id": candidate.id,
                    "payload_priority": priority,
                    "candidate_priority": candidate.priority,
                },
            )
        )

    missing_fields, mismatched_fields = _candidate_source_mismatches(item, candidate)
    if missing_fields or mismatched_fields:
        issues.append(
            DailyAdviceValidationIssue(
                code="candidate_source_mismatch",
                message="每日建议候选来源字段与 selected candidate 不一致。",
                path=item_path,
                evidence={
                    "item_id": candidate.id,
                    "missing_fields": missing_fields,
                    "fields": mismatched_fields,
                    "expected": {
                        field_name: getattr(candidate, field_name)
                        for field_name in mismatched_fields
                    },
                    "actual": {
                        field_name: item.get(field_name)
                        for field_name in mismatched_fields
                    },
                },
            )
        )


def validate_top_level_shape(
    payload: dict[str, Any],
    issues: list[DailyAdviceValidationIssue],
) -> None:
    missing_fields = [
        field_name
        for field_name in _REQUIRED_TOP_LEVEL_FIELDS
        if field_name not in payload
    ]
    if missing_fields:
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="DailyAdvice v2 payload 缺少必需顶层字段。",
                path="$",
                evidence={"missing_fields": missing_fields},
            )
        )

    overview = payload.get("overview")
    if not isinstance(overview, dict):
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="DailyAdvice payload.overview 必须是 dict。",
                path="overview",
                evidence={"actual_type": type(overview).__name__},
            )
        )
    else:
        _validate_overview_shape(overview, issues)

    generation = payload.get("generation")
    if not isinstance(generation, dict):
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="DailyAdvice payload.generation 必须是 dict。",
                path="generation",
                evidence={"actual_type": type(generation).__name__},
            )
        )
        return

    schema_version = generation.get("schema_version")
    if schema_version != "daily_advice_v2":
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="DailyAdvice generation.schema_version 必须是 daily_advice_v2。",
                path="generation.schema_version",
                evidence={"actual": schema_version},
            )
        )


def collect_forbidden_topic_issues(
    payload: dict[str, Any],
    issues: list[DailyAdviceValidationIssue],
) -> None:
    for path, text in _iter_text_fields(payload):
        for term in FORBIDDEN_DAILY_ADVICE_TERMS:
            if term in text:
                issues.append(
                    DailyAdviceValidationIssue(
                        code="forbidden_daily_advice_topic",
                        message="每日建议包含禁止主题或禁止词。",
                        path=path,
                        evidence={"term": term, "text_preview": text[:120]},
                    )
                )


def _collect_text_thin_reasons(
    compact: dict[str, Any],
    detail_view: dict[str, Any],
    item_path: str,
    thin_reasons: list[dict[str, Any]],
) -> None:
    thin_reasons.extend(
        collect_text_bounds_reasons(
            (
                (f"{item_path}.compact.title", compact.get("title"), 1, 12),
                (f"{item_path}.compact.subtitle", compact.get("subtitle"), 15, 50),
                (f"{item_path}.detail_view.title", detail_view.get("title"), 1, 120),
                (
                    f"{item_path}.detail_view.description",
                    detail_view.get("description"),
                    20,
                    120,
                ),
            )
        )
    )

def _collect_steps_thin_reasons(
    detail_view: dict[str, Any],
    item_path: str,
    thin_reasons: list[dict[str, Any]],
) -> None:
    steps = detail_view.get("steps")
    if not isinstance(steps, list) or len(steps) < 2:
        thin_reasons.append(
            {
                "field": f"{item_path}.detail_view.steps",
                "min_count": 2,
                "actual_count": len(steps) if isinstance(steps, list) else None,
            }
        )
        return

    thin_reasons.extend(_step_completeness_reasons(steps, item_path))


def _collect_actions_thin_reasons(
    detail_view: dict[str, Any],
    item_path: str,
    thin_reasons: list[dict[str, Any]],
) -> None:
    if not _includes_ask_agent(detail_view.get("actions")):
        thin_reasons.append(
            {
                "field": f"{item_path}.detail_view.actions",
                "required": "ask_agent",
            }
        )


def _collect_evidence_thin_reasons(
    detail_view: dict[str, Any],
    item_path: str,
    mode: str,
    thin_reasons: list[dict[str, Any]],
) -> None:
    evidence = detail_view.get("evidence")
    if mode in _EMPTY_MODES:
        return
    if not isinstance(evidence, list) or len(evidence) < 1:
        thin_reasons.append(
            {
                "field": f"{item_path}.detail_view.evidence",
                "min_count": 1,
                "actual_count": len(evidence) if isinstance(evidence, list) else None,
            }
        )
        return
    thin_reasons.extend(_evidence_completeness_reasons(evidence, item_path))


def _validate_overview_shape(
    overview: dict[str, Any],
    issues: list[DailyAdviceValidationIssue],
) -> None:
    metrics = overview.get("metrics")
    if not isinstance(metrics, list):
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="DailyAdvice overview.metrics 必须是 list。",
                path="overview.metrics",
                evidence={"actual_type": type(metrics).__name__},
            )
        )
        return

    metric_keys = {
        metric.get("key")
        for metric in metrics
        if isinstance(metric, dict) and isinstance(metric.get("key"), str)
    }
    missing_metric_keys = sorted(_REQUIRED_OVERVIEW_METRIC_KEYS - metric_keys)
    if missing_metric_keys:
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="DailyAdvice overview.metrics 缺少必需指标 key。",
                path="overview.metrics",
                evidence={"missing_keys": missing_metric_keys},
            )
        )


def _priority_issue(
    priority: Any,
    item_path: str,
    candidate: DailyAdviceCandidate,
) -> DailyAdviceValidationIssue | None:
    if priority is None:
        return DailyAdviceValidationIssue(
            code="priority_escalation_not_allowed",
            message="每日建议 priority 必须存在。",
            path=f"{item_path}.priority",
            evidence={"item_id": candidate.id, "invalid_reason": "missing"},
        )

    if not isinstance(priority, int):
        return DailyAdviceValidationIssue(
            code="priority_escalation_not_allowed",
            message="每日建议 priority 必须是 int。",
            path=f"{item_path}.priority",
            evidence={
                "item_id": candidate.id,
                "invalid_reason": "not_int",
                "actual_type": type(priority).__name__,
            },
        )

    if priority < 1 or priority > 3:
        return DailyAdviceValidationIssue(
            code="priority_escalation_not_allowed",
            message="每日建议 priority 必须在 1..3 范围内。",
            path=f"{item_path}.priority",
            evidence={
                "item_id": candidate.id,
                "invalid_reason": "out_of_range",
                "payload_priority": priority,
            },
        )

    return None


def _candidate_source_mismatches(
    item: dict[str, Any],
    candidate: DailyAdviceCandidate,
) -> tuple[list[str], list[str]]:
    missing_fields = []
    mismatched_fields = []
    for field_name in ("category", "source_type", "source_id"):
        if field_name not in item:
            missing_fields.append(field_name)
            continue
        if item.get(field_name) != getattr(candidate, field_name):
            mismatched_fields.append(field_name)
    return missing_fields, mismatched_fields


def _step_completeness_reasons(
    steps: list[Any],
    item_path: str,
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for index, step in enumerate(steps):
        field = f"{item_path}.detail_view.steps[{index}]"
        if not isinstance(step, dict):
            reasons.append(
                {
                    "field": field,
                    "required": "dict",
                    "actual_type": type(step).__name__,
                }
            )
            continue

        missing_or_invalid: list[str] = []
        title = step.get("title")
        if not isinstance(title, str) or not title.strip():
            missing_or_invalid.append("title")
        order = step.get("order")
        if not isinstance(order, int) or order < 1:
            missing_or_invalid.append("order")
        if missing_or_invalid:
            reasons.append(
                {
                    "field": field,
                    "missing_or_invalid": missing_or_invalid,
                }
            )
    return reasons


def _evidence_completeness_reasons(
    evidence_items: list[Any],
    item_path: str,
) -> list[dict[str, Any]]:
    reasons: list[dict[str, Any]] = []
    for index, evidence in enumerate(evidence_items):
        field = f"{item_path}.detail_view.evidence[{index}]"
        if not isinstance(evidence, dict):
            reasons.append(
                {
                    "field": field,
                    "required": "dict",
                    "actual_type": type(evidence).__name__,
                }
            )
            continue

        missing_or_invalid: list[str] = []
        for field_name in ("title", "description", "source_type"):
            value = evidence.get(field_name)
            if not isinstance(value, str) or not value.strip():
                missing_or_invalid.append(field_name)
        if missing_or_invalid:
            reasons.append(
                {
                    "field": field,
                    "missing_or_invalid": missing_or_invalid,
                }
            )
    return reasons


def _iter_text_fields(value: Any, path: str = "$"):
    if isinstance(value, str):
        yield path, value
        return
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _iter_text_fields(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _iter_text_fields(child, f"{path}[{index}]")


def _includes_ask_agent(actions: Any) -> bool:
    if not isinstance(actions, list):
        return False
    return any(
        isinstance(action, dict) and action.get("type") == "ask_agent"
        for action in actions
    )
