"""每日建议 v2 生成结果硬校验入口。"""

from __future__ import annotations

from app.domains.conversation.daily_advice_models import DailyAdviceCandidate
from app.domains.conversation.daily_advice_validation_checks import (
    collect_forbidden_topic_issues,
    validate_candidate_fields,
    validate_candidate_identity,
    validate_content_completeness,
    validate_top_level_shape,
)
from app.domains.conversation.daily_advice_validation_models import (
    FORBIDDEN_DAILY_ADVICE_TERMS,
    DailyAdviceValidationIssue,
    DailyAdviceValidationResult,
    build_validation_result,
)


def validate_daily_advice_payload(
    payload: dict,
    candidates: list[DailyAdviceCandidate],
    *,
    generation_mode: str = "llm",
) -> DailyAdviceValidationResult:
    """校验 LLM 生成的每日建议 v2 payload。"""
    issues: list[DailyAdviceValidationIssue] = []
    candidate_by_id = {candidate.id: candidate for candidate in candidates}

    if not isinstance(payload, dict):
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="DailyAdvice payload 必须是 dict。",
                path="$",
                evidence={"actual_type": type(payload).__name__},
            )
        )
        return build_validation_result(issues, candidates)

    collect_forbidden_topic_issues(payload, issues)
    validate_top_level_shape(payload, issues)

    items = payload.get("items")
    if not isinstance(items, list):
        issues.append(
            DailyAdviceValidationIssue(
                code="invalid_payload_shape",
                message="DailyAdvice payload.items 必须是 list。",
                path="items",
                evidence={"actual_type": type(items).__name__},
            )
        )
        return build_validation_result(issues, candidates)

    if not items:
        issues.append(
            DailyAdviceValidationIssue(
                code="empty_daily_advice_items",
                message="DailyAdvice payload.items 不能为空。",
                path="items",
            )
        )
        return build_validation_result(issues, candidates)

    for index, item in enumerate(items):
        item_path = f"items[{index}]"
        if not isinstance(item, dict):
            issues.append(
                DailyAdviceValidationIssue(
                    code="invalid_payload_shape",
                    message="DailyAdvice item 必须是 dict。",
                    path=item_path,
                    evidence={"actual_type": type(item).__name__},
                )
            )
            continue

        candidate = validate_candidate_identity(
            item=item,
            item_path=item_path,
            candidate_by_id=candidate_by_id,
            issues=issues,
        )
        validate_content_completeness(item, item_path, generation_mode, issues)
        if candidate is not None:
            validate_candidate_fields(item, item_path, candidate, issues)

    return build_validation_result(issues, candidates)


__all__ = [
    "FORBIDDEN_DAILY_ADVICE_TERMS",
    "DailyAdviceValidationIssue",
    "DailyAdviceValidationResult",
    "validate_daily_advice_payload",
]
