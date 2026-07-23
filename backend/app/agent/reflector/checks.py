"""Agent Reflection 规则检查。"""

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from langchain_core.messages import ToolMessage

from app.agent.reflector.models import (
    ReflectionDecision,
    ReflectionIssue,
    ReflectionResult,
    ReflectionSeverity,
    ReflectionTrigger,
)
from app.infra.pending_actions import PendingPlanStep, is_write_skill

_SUCCESS_HINTS = ("已执行", "成功", "已创建", "已保存", "已更新", "完成")
_FAILURE_HINTS = ("失败", "错误", "异常", "validation", "参数校验失败", "工具调用失败")
_BUSINESS_ENTITY_HINTS = ("茬口", "工人", "欠款", "金额", "模板")
_BUSINESS_DATA_ASSERTION_HINTS = (
    "现有",
    "已有",
    "现在有",
    "当前有",
    "目前有",
    "当前共有",
    "目前共有",
    "共有",
    "总共",
    "合计",
    "当前没有",
    "目前没有",
    "没有模板",
    "没有茬口",
    "没有欠款",
    "没有工人",
    "暂无",
    "未找到",
    "查到",
    "查询到",
    "系统里",
    "记录里",
    "数据库",
    "列表里",
    "模板库",
)
_BUSINESS_QUANTITY_HINTS = ("共", "总", "当前共有", "现在有")
_WRITE_PLAN_CHECK = "write_plan_consistency"
_PENDING_PLAN_CHECK = "pending_plan_consistency"
_TOOL_RESPONSE_CHECK = "tool_failure_success_reply"
_WRITE_PLAN_TOOL_FAILURE_CHECK = "write_plan_tool_failure_reply"
_TOOL_CONCLUSION_CHECK = "tool_result_final_contradiction"
_REQUIRED_TOOL_CHECK = "required_tool_missing"
_NO_TOOL_WRITE_SUCCESS_CHECK = "no_tool_write_success_claim"
_NO_TOOL_NEEDED_HINTS = ("不需要调用工具", "无需调用工具", "可以直接聊", "直接聊")
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?(?![A-Za-z0-9.])")
_WRITE_SUCCESS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("已为您记录", re.compile(r"已为(?:你|您)?记录")),
    (
        "已记录",
        re.compile(r"(?:^|[，,。；;！!\n])\s*(?:已|已经)(?:帮你|为你|为您)?记录"),
    ),
    ("已创建", re.compile(r"(?:已|已经)(?:帮你|为你|为您)?创建")),
    ("已保存", re.compile(r"(?:已|已经)(?:帮你|为你|为您)?保存")),
    ("已执行", re.compile(r"(?:已|已经)(?:帮你|为你|为您)?执行")),
)


def check_write_plan_consistency(
    *,
    trigger: ReflectionTrigger,
    skill_name: str,
    params: dict[str, Any],
    confirmation_text: str,
) -> ReflectionResult:
    if is_write_skill(skill_name) and not params:
        return _single_issue(
            trigger=trigger,
            decision=ReflectionDecision.ASK_CLARIFICATION,
            checks=[_WRITE_PLAN_CHECK],
            code="empty_write_params",
            message=f"{skill_name} 是写操作，但参数为空。",
            evidence={"skill_name": skill_name},
        )

    mismatch = _find_confirmation_mismatch(params, confirmation_text)
    if mismatch is not None:
        return _single_issue(
            trigger=trigger,
            decision=ReflectionDecision.BLOCK_WRITE,
            checks=[_WRITE_PLAN_CHECK],
            code="confirmation_param_mismatch",
            message="确认文案与待执行参数不一致。",
            evidence=mismatch,
        )

    return ReflectionResult.passed(trigger, checks=[_WRITE_PLAN_CHECK])


def check_pending_plan_consistency(
    *,
    trigger: ReflectionTrigger,
    steps: list[PendingPlanStep],
    confirmation_text: str,
) -> ReflectionResult:
    if not steps:
        return _single_issue(
            trigger=trigger,
            decision=ReflectionDecision.BLOCK_WRITE,
            checks=[_PENDING_PLAN_CHECK],
            code="empty_pending_plan",
            message="待确认计划没有步骤。",
            evidence={},
        )

    step_ids = {step.step_id for step in steps}
    for step in steps:
        if is_write_skill(step.tool_name) and not step.params:
            return _single_issue(
                trigger=trigger,
                decision=ReflectionDecision.ASK_CLARIFICATION,
                checks=[_PENDING_PLAN_CHECK],
                code="empty_write_params",
                message=f"{step.tool_name} 是写操作，但参数为空。",
                evidence={"step_id": step.step_id, "tool_name": step.tool_name},
            )
        missing_deps = [dep for dep in step.depends_on if dep not in step_ids]
        if missing_deps:
            return _single_issue(
                trigger=trigger,
                decision=ReflectionDecision.BLOCK_WRITE,
                checks=[_PENDING_PLAN_CHECK],
                code="missing_plan_dependency",
                message="待确认计划存在不存在的依赖步骤。",
                evidence={"step_id": step.step_id, "missing_depends_on": missing_deps},
            )

    if str(len(steps)) not in confirmation_text:
        return _single_issue(
            trigger=trigger,
            decision=ReflectionDecision.BLOCK_WRITE,
            checks=[_PENDING_PLAN_CHECK],
            code="plan_confirmation_step_count_mismatch",
            message="确认文案中的步骤数量与实际计划不一致。",
            evidence={
                "steps": len(steps),
                "confirmation_text": confirmation_text[:120],
            },
        )

    return ReflectionResult.passed(trigger, checks=[_PENDING_PLAN_CHECK])


def check_tool_failure_success_reply(
    *,
    tool_messages: list[ToolMessage],
    final_text: str,
) -> ReflectionResult:
    failed = [
        str(message.content or "")
        for message in tool_messages
        if _contains_any(str(message.content or ""), _FAILURE_HINTS)
    ]
    if failed and _contains_any(final_text, _SUCCESS_HINTS):
        return _single_issue(
            trigger=ReflectionTrigger.POST_TOOL_RESULT,
            decision=ReflectionDecision.FALLBACK_RESPONSE,
            checks=[_TOOL_RESPONSE_CHECK],
            code="failed_tool_success_reply",
            message="工具结果失败，但最终回复声称成功。",
            evidence={
                "failed_tool_message": failed[0][:160],
                "final_text": final_text[:160],
            },
        )
    return ReflectionResult.passed(
        ReflectionTrigger.POST_TOOL_RESULT,
        checks=[_TOOL_RESPONSE_CHECK],
    )


def check_tool_failure_write_plan_reply(
    *,
    tool_messages: list[ToolMessage],
    final_text: str,
    plan_draft: dict[str, Any] | None = None,
    pending_created: bool | None = None,
) -> ReflectionResult:
    failed = [
        str(message.content or "")
        for message in tool_messages
        if _contains_any(str(message.content or ""), _FAILURE_HINTS)
    ]
    if not failed:
        return ReflectionResult.passed(
            ReflectionTrigger.POST_TOOL_RESULT,
            checks=[_WRITE_PLAN_TOOL_FAILURE_CHECK],
        )
    if not _is_write_plan(plan_draft) or pending_created:
        return ReflectionResult.passed(
            ReflectionTrigger.POST_TOOL_RESULT,
            checks=[_WRITE_PLAN_TOOL_FAILURE_CHECK],
        )
    if not _contains_any(final_text, _NO_TOOL_NEEDED_HINTS):
        return ReflectionResult.passed(
            ReflectionTrigger.POST_TOOL_RESULT,
            checks=[_WRITE_PLAN_TOOL_FAILURE_CHECK],
        )
    return _single_issue(
        trigger=ReflectionTrigger.POST_TOOL_RESULT,
        decision=ReflectionDecision.FALLBACK_RESPONSE,
        checks=[_WRITE_PLAN_TOOL_FAILURE_CHECK],
        code="failed_write_plan_no_tool_reply",
        message="写入计划的工具调用失败，但最终回复淡化了工具和待确认动作需求。",
        evidence={
            "failed_tool_message": failed[0][:160],
            "final_text": final_text[:160],
            "plan_draft": _summarize_plan_draft(plan_draft),
            "pending_created": pending_created,
        },
    )


def check_required_tool_missing(
    *,
    selected_tools: list[str],
    tool_calls: list[dict[str, Any]],
    final_text: str,
) -> ReflectionResult:
    if not selected_tools:
        return ReflectionResult.passed(
            ReflectionTrigger.PRE_FINAL_RESPONSE,
            checks=[_REQUIRED_TOOL_CHECK],
        )
    if tool_calls:
        return ReflectionResult.passed(
            ReflectionTrigger.PRE_FINAL_RESPONSE,
            checks=[_REQUIRED_TOOL_CHECK],
        )
    if not _looks_like_business_fact(final_text):
        return ReflectionResult.passed(
            ReflectionTrigger.PRE_FINAL_RESPONSE,
            checks=[_REQUIRED_TOOL_CHECK],
        )

    return _single_issue(
        trigger=ReflectionTrigger.PRE_FINAL_RESPONSE,
        decision=ReflectionDecision.REQUIRE_TOOL,
        checks=[_REQUIRED_TOOL_CHECK],
        code="required_tool_missing",
        message="Router 已选择工具，但回复直接给出了需要真实数据支撑的业务事实。",
        evidence={"selected_tools": selected_tools, "final_text": final_text[:160]},
    )


def check_no_tool_write_success_claim(
    *,
    user_message: str,
    final_text: str,
    selected_tools: list[str],
    tool_messages: list[ToolMessage],
    tool_calls: list[dict[str, Any]],
    plan_draft: dict[str, Any] | None = None,
    pending_created: bool | None = None,
) -> ReflectionResult:
    if selected_tools or tool_messages or tool_calls:
        return ReflectionResult.passed(
            ReflectionTrigger.FALLBACK_GUARD,
            checks=[_NO_TOOL_WRITE_SUCCESS_CHECK],
        )

    matched_phrase = first_write_success_phrase(final_text)
    if matched_phrase is None:
        return ReflectionResult.passed(
            ReflectionTrigger.FALLBACK_GUARD,
            checks=[_NO_TOOL_WRITE_SUCCESS_CHECK],
        )

    return _single_issue(
        trigger=ReflectionTrigger.FALLBACK_GUARD,
        decision=ReflectionDecision.FALLBACK_RESPONSE,
        checks=[_NO_TOOL_WRITE_SUCCESS_CHECK],
        code="no_tool_write_success_claim",
        message=("没有工具写入结果或待确认动作，但最终回复声称业务数据已经写入。"),
        evidence={
            "user_message": user_message[:160],
            "final_text": final_text[:160],
            "matched_success_phrase": matched_phrase,
            "selected_tools": selected_tools,
            "tool_messages_count": len(tool_messages),
            "tool_calls_count": len(tool_calls),
            "failure_stage": "response_quality",
            "plan_draft": _summarize_plan_draft(plan_draft),
            "pending_created": pending_created,
        },
    )


def _summarize_plan_draft(plan_draft: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(plan_draft, dict):
        return {}
    validation = plan_draft.get("validation")
    if not isinstance(validation, dict):
        validation = {}
    return {
        "route_type": plan_draft.get("route_type", ""),
        "validation_status": validation.get("status")
        or plan_draft.get("validation_status", ""),
        "missing_fields": _string_list(
            plan_draft.get("missing_fields") or validation.get("missing_fields")
        ),
        "steps": _plan_step_names(plan_draft.get("steps")),
        "evidence": plan_draft.get("evidence") or {},
    }


def _is_write_plan(plan_draft: dict[str, Any] | None) -> bool:
    if not isinstance(plan_draft, dict):
        return False
    route_type = str(plan_draft.get("route_type") or "")
    return route_type.startswith("write_")


def _plan_step_names(steps: Any) -> list[str]:
    if not isinstance(steps, list):
        return []
    names: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        name = step.get("tool_name") or step.get("skill_name") or step.get("name")
        if name:
            names.append(str(name))
    return names


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item]


def check_tool_result_final_contradiction(
    *,
    tool_messages: list[ToolMessage],
    final_text: str,
) -> ReflectionResult:
    tool_numbers = _extract_numbers_from_messages(tool_messages)
    final_numbers = _extract_numbers(final_text)
    if not tool_numbers or not final_numbers:
        return ReflectionResult.passed(
            ReflectionTrigger.POST_TOOL_RESULT,
            checks=[_TOOL_CONCLUSION_CHECK],
        )
    if any(number in tool_numbers for number in final_numbers):
        return ReflectionResult.passed(
            ReflectionTrigger.POST_TOOL_RESULT,
            checks=[_TOOL_CONCLUSION_CHECK],
        )
    return _single_issue(
        trigger=ReflectionTrigger.POST_TOOL_RESULT,
        decision=ReflectionDecision.FALLBACK_RESPONSE,
        checks=[_TOOL_CONCLUSION_CHECK],
        code="tool_result_final_contradiction",
        message="工具结果与最终回复中的关键数量不一致。",
        evidence={
            "tool_numbers": [str(number) for number in tool_numbers],
            "final_numbers": [str(number) for number in final_numbers],
            "final_text": final_text[:160],
        },
    )


def _find_confirmation_mismatch(
    params: dict[str, Any],
    confirmation_text: str,
) -> dict[str, Any] | None:
    for field in ("amount", "unit_price", "default_unit_price", "paid_amount"):
        value = params.get(field)
        if value in (None, ""):
            continue
        normalized = _normalize_decimal(value)
        if normalized is None:
            continue
        if _decimal_text_present(normalized, confirmation_text):
            continue
        return {
            "field": field,
            "param_value": str(value),
            "confirmation_text": confirmation_text[:160],
        }
    return None


def _normalize_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)).normalize()
    except (InvalidOperation, ValueError):
        return None


def _decimal_text_present(value: Decimal, text: str) -> bool:
    tokens = (_normalize_decimal(match.group(0)) for match in _NUMBER_RE.finditer(text))
    return any(token == value for token in tokens if token is not None)


def _extract_numbers_from_messages(messages: list[ToolMessage]) -> set[Decimal]:
    numbers: set[Decimal] = set()
    for message in messages:
        numbers.update(_extract_numbers(str(message.content or "")))
    return numbers


def _extract_numbers(text: str) -> set[Decimal]:
    return {
        number
        for number in (
            _normalize_decimal(match.group(0)) for match in _NUMBER_RE.finditer(text)
        )
        if number is not None
    }


def _contains_any(text: str, hints: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(hint.lower() in lowered for hint in hints)


def _looks_like_business_fact(text: str) -> bool:
    if not _contains_any(text, _BUSINESS_ENTITY_HINTS):
        return False
    if _contains_any(text, _BUSINESS_DATA_ASSERTION_HINTS):
        return True
    return bool(_extract_numbers(text)) and _contains_any(
        text, _BUSINESS_QUANTITY_HINTS
    )


def first_write_success_phrase(text: str) -> str | None:
    for phrase, pattern in _WRITE_SUCCESS_PATTERNS:
        if pattern.search(text):
            return phrase
    return None


def _single_issue(
    *,
    trigger: ReflectionTrigger,
    decision: ReflectionDecision,
    checks: list[str],
    code: str,
    message: str,
    evidence: dict[str, Any],
) -> ReflectionResult:
    return ReflectionResult(
        trigger=trigger,
        decision=decision,
        checks=checks,
        reason=message,
        issues=[
            ReflectionIssue(
                code=code,
                severity=ReflectionSeverity.BLOCKER,
                message=message,
                evidence=evidence,
                suggested_decision=decision,
            )
        ],
    )
