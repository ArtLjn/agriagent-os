"""Agent Reflection 规则检查。"""

from collections.abc import Iterable, Mapping, Sequence
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
_TOOL_RESULT_DISCARDED_CHECK = "tool_result_discarded_reply"
_TOOL_CONCLUSION_CHECK = "tool_result_final_contradiction"
_REQUIRED_TOOL_CHECK = "required_tool_missing"
_NO_TOOL_WRITE_SUCCESS_CHECK = "no_tool_write_success_claim"
_NO_TOOL_NEEDED_HINTS = ("不需要调用工具", "无需调用工具", "可以直接聊", "直接聊")
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?(?![A-Za-z0-9.])")
_CLAUSE_SPLIT_RE = re.compile(r"[。！？；;，,\n]+")
_WRITE_SUCCESS_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("已为您记录", re.compile(r"已为(?:你|您)?记录")),
    (
        "已记录",
        re.compile(r"(?:^|[，,。；;！!\n])\s*(?:已|已经)(?:帮你|为你|为您)?记录"),
    ),
    ("已创建", re.compile(r"(?:已|已经)(?:帮你|为你|为您)?创建")),
    ("这就创建", re.compile(r"这就(?:帮你|为你|为您)?[^。！？\n]*创建")),
    ("已保存", re.compile(r"(?:已|已经)(?:帮你|为你|为您)?保存")),
    ("已执行", re.compile(r"(?:已|已经)(?:帮你|为你|为您)?执行")),
)
_NON_TOOL_FACT_SOURCE_KINDS = {"user_input", "memory", "rag", "derived", "system"}
_FACT_KEY_CLAUSE_HINTS: dict[str, tuple[str, ...]] = {
    "total_area_mu": ("面积", "亩", "地"),
    "unit_area_mu": ("每块", "单块", "块地", "亩"),
    "unit_count": ("拆分", "规划", "计划", "安排", "地块", "块", "茬口"),
}
_PLANNED_UNIT_HINTS = ("拆分", "规划", "计划", "安排")


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


def check_tool_result_discarded_reply(
    *,
    tool_messages: list[ToolMessage],
    final_text: str,
) -> ReflectionResult:
    if not tool_messages or not _contains_any(final_text, _NO_TOOL_NEEDED_HINTS):
        return ReflectionResult.passed(
            ReflectionTrigger.POST_TOOL_RESULT,
            checks=[_TOOL_RESULT_DISCARDED_CHECK],
        )
    return _single_issue(
        trigger=ReflectionTrigger.POST_TOOL_RESULT,
        decision=ReflectionDecision.RETRY_GENERATION,
        checks=[_TOOL_RESULT_DISCARDED_CHECK],
        code="tool_result_discarded_reply",
        message="当前轮已有工具结果，但最终回复淡化或丢弃了工具结果。",
        evidence={
            "tool_message_count": len(tool_messages),
            "final_text": final_text[:160],
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
    if tool_messages or tool_calls or pending_created is True:
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
    fact_sources: Any | None = None,
) -> ReflectionResult:
    if not _looks_like_business_fact(final_text):
        return ReflectionResult.passed(
            ReflectionTrigger.POST_TOOL_RESULT,
            checks=[_TOOL_CONCLUSION_CHECK],
        )
    tool_numbers = _extract_numbers_from_messages(tool_messages)
    allowed_facts = _extract_non_tool_facts(fact_sources)
    final_numbers, allowed_fact_numbers = _extract_unprotected_asserted_numbers(
        final_text,
        allowed_facts,
    )
    if not tool_numbers or not final_numbers:
        return ReflectionResult.passed(
            ReflectionTrigger.POST_TOOL_RESULT,
            checks=[_TOOL_CONCLUSION_CHECK],
        )
    if final_numbers.issubset(tool_numbers):
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
            "allowed_fact_numbers": [str(number) for number in allowed_fact_numbers],
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


def _extract_unprotected_asserted_numbers(
    text: str,
    allowed_facts: list[dict[str, Any]],
) -> tuple[set[Decimal], set[Decimal]]:
    unprotected: set[Decimal] = set()
    protected: set[Decimal] = set()
    for clause in _business_fact_clauses(text):
        for number in _extract_numbers(clause):
            if _number_allowed_by_fact_clause(number, clause, allowed_facts):
                protected.add(number)
            else:
                unprotected.add(number)
    return unprotected, protected


def _number_allowed_by_fact_clause(
    number: Decimal,
    clause: str,
    allowed_facts: list[dict[str, Any]],
) -> bool:
    return any(
        number in fact["numbers"] and _fact_key_matches_clause(fact["key"], clause)
        for fact in allowed_facts
    )


def _fact_key_matches_clause(key: str, clause: str) -> bool:
    hints = _FACT_KEY_CLAUSE_HINTS.get(key)
    if hints is None:
        return bool(key) and key in clause
    if key == "unit_count" and "茬口" in clause:
        return any(hint in clause for hint in _PLANNED_UNIT_HINTS)
    return any(hint in clause for hint in hints)


def _extract_non_tool_facts(fact_sources: Any | None) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for key, fact in _iter_fact_source_items(fact_sources):
        if _fact_source_kind(fact) not in _NON_TOOL_FACT_SOURCE_KINDS:
            continue
        numbers = _extract_fact_value_numbers(_fact_value(fact))
        if numbers:
            facts.append({"key": _fact_key(key, fact), "numbers": numbers})
    return facts


def _iter_fact_source_items(
    value: Any, key: str | None = None
) -> Iterable[tuple[str | None, Any]]:
    if value is None:
        return
    if _looks_like_fact_source_item(value):
        yield key, value
        return
    if isinstance(value, Mapping):
        for nested_key, nested in value.items():
            yield from _iter_fact_source_items(nested, str(nested_key))
        return
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        for nested in value:
            yield from _iter_fact_source_items(nested, key)


def _looks_like_fact_source_item(value: Any) -> bool:
    if isinstance(value, Mapping):
        return "value" in value and "source" in value
    return hasattr(value, "value") and hasattr(value, "source")


def _fact_source_kind(fact: Any) -> str | None:
    source = (
        fact.get("source")
        if isinstance(fact, Mapping)
        else getattr(fact, "source", None)
    )
    if isinstance(source, str):
        kind = source
    elif isinstance(source, Mapping):
        kind = source.get("kind")
    else:
        kind = getattr(source, "kind", None)
    return str(kind) if kind else None


def _fact_key(key: str | None, fact: Any) -> str:
    if isinstance(fact, Mapping):
        explicit_key = fact.get("name") or fact.get("key")
    else:
        explicit_key = getattr(fact, "name", None) or getattr(fact, "key", None)
    return str(explicit_key or key or "")


def _fact_value(fact: Any) -> Any:
    if isinstance(fact, Mapping):
        return fact.get("value")
    return getattr(fact, "value", None)


def _extract_fact_value_numbers(value: Any) -> set[Decimal]:
    if value is None or isinstance(value, bool):
        return set()
    if isinstance(value, int | float | Decimal):
        normalized = _normalize_decimal(value)
        return {normalized} if normalized is not None else set()
    if isinstance(value, str):
        return _extract_numbers(value)
    if isinstance(value, Mapping):
        numbers: set[Decimal] = set()
        for nested in value.values():
            numbers.update(_extract_fact_value_numbers(nested))
        return numbers
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        numbers: set[Decimal] = set()
        for nested in value:
            numbers.update(_extract_fact_value_numbers(nested))
        return numbers
    return set()


def _business_fact_clauses(text: str) -> list[str]:
    return [
        clause.strip()
        for clause in _CLAUSE_SPLIT_RE.split(text)
        if _looks_like_business_fact(clause)
    ]


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
