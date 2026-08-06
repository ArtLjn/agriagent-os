"""每日建议生成 Reflection 检查。"""

from __future__ import annotations

import logging
import time
from typing import Any

from app.agent.reflector.models import (
    ReflectionDecision,
    ReflectionIssue,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
)
from app.infra.trace_collector import get_collector
from app.domains.conversation.daily_advice_models import DailyAdviceCandidate
from app.domains.conversation.daily_advice_validation import (
    DailyAdviceValidationIssue,
    validate_daily_advice_payload,
)

logger = logging.getLogger(__name__)

_DAILY_ADVICE_GENERATION_CHECK = "daily_advice_generation"


def check_daily_advice_generation(
    payload: Any,
    candidates: list[DailyAdviceCandidate],
    *,
    farm_id: int,
    candidate_fingerprint: str,
    retry_index: int,
    generation_mode: str,
    trace_metadata: dict[str, Any] | None = None,
) -> ReflectionResult:
    """把每日建议 validator 结果转换为 ReflectionResult 并记录 trace。"""
    validation = validate_daily_advice_payload(
        payload,
        candidates,
        generation_mode=generation_mode,
    )
    metadata = {
        "valid": validation.valid,
        "repair_instruction": validation.repair_instruction,
        "candidate_ids": [candidate.id for candidate in candidates],
        "farm_id": farm_id,
        "candidate_fingerprint": candidate_fingerprint,
        "retry_index": retry_index,
        "generation_mode": generation_mode,
    }
    if trace_metadata:
        metadata["extra"] = trace_metadata

    if validation.valid:
        result = ReflectionResult.passed(
            ReflectionTrigger.PRE_FINAL_RESPONSE,
            reason="每日建议生成校验通过。",
            checks=[_DAILY_ADVICE_GENERATION_CHECK],
            metadata=metadata,
        )
        return _record_daily_advice_reflection(result)

    result = ReflectionResult(
        trigger=ReflectionTrigger.PRE_FINAL_RESPONSE,
        decision=ReflectionDecision.RETRY_GENERATION,
        checks=[_DAILY_ADVICE_GENERATION_CHECK],
        reason="每日建议生成校验未通过，需要重试生成。",
        issues=[
            _to_reflection_issue(issue)
            for issue in validation.issues
        ],
        metadata=metadata,
    )
    return _record_daily_advice_reflection(result)


def _to_reflection_issue(issue: DailyAdviceValidationIssue) -> ReflectionIssue:
    return ReflectionIssue(
        code=issue.code,
        severity=ReflectionSeverity.BLOCKER,
        message=issue.message,
        evidence={
            "path": issue.path,
            **issue.evidence,
        },
        suggested_decision=ReflectionDecision.RETRY_GENERATION,
    )


def _record_daily_advice_reflection(result: ReflectionResult) -> ReflectionResult:
    start = time.time()
    try:
        get_collector().record(
            node_type="reflection_check",
            node_name=_DAILY_ADVICE_GENERATION_CHECK,
            input_data=result.metadata,
            output_data=result.to_trace_payload(),
            start_time=start,
            end_time=time.time(),
        )
    except Exception as exc:
        logger.warning("DailyAdvice Reflection trace 记录失败 | error=%s", exc)
    return result


__all__ = ["check_daily_advice_generation"]
