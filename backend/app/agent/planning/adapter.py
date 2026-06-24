"""PlanDraft 兼容适配器。"""

from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any

from app.agent.planning.models import PlanDraft, PlanIssue, PlanStep, PlanValidationResult
from app.agent.router.models import IntentFrame, RouterDecision


def plan_draft_from_router_decision(
    *,
    raw_user_input: str,
    decision: RouterDecision,
    farm_id: int | None = None,
    session_id: str | None = None,
    turn_id: str = "",
) -> PlanDraft:
    """把现有 RouterDecision 适配成 PlanDraft。"""
    missing_fields = _collect_missing_fields(decision.frames)
    evidence = _merge_evidence(decision.frames)
    steps = _steps_from_frames(decision.frames)
    route_type = _route_type_for_decision(decision, steps, missing_fields)
    validation = _initial_validation(route_type, missing_fields)

    return PlanDraft(
        turn_id=turn_id,
        session_id=session_id or "",
        farm_id=farm_id or 0,
        raw_user_input=raw_user_input,
        route_type=route_type,
        source="rule_gate",
        intent_frames=[asdict(frame) for frame in decision.frames],
        steps=steps,
        evidence={
            **evidence,
            "selected_tools": list(decision.selected_tools),
            "fallback": decision.fallback,
            "policy_violations": list(decision.policy_violations),
        },
        missing_fields=missing_fields,
        selected_tools=list(decision.selected_tools),
        validation=validation,
    )


def attach_validation(
    draft: PlanDraft,
    validation: PlanValidationResult,
) -> PlanDraft:
    """附加验证结果，并把阻塞路由降级为 clarification。"""
    return replace(
        draft,
        route_type=validation.safe_route_type,
        missing_fields=list(validation.missing_fields),
        validation=validation,
    )


def _route_type_for_decision(
    decision: RouterDecision,
    steps: list[PlanStep],
    missing_fields: list[str],
):
    if decision.clarification or decision.fallback in {
        "clarify_farm_labor_work",
        "clarify_write_intent",
    }:
        return "clarification"
    if "operation_type" in missing_fields:
        return "clarification"
    if steps:
        write_steps = [step for step in steps if step.risk.startswith("write")]
        if len(write_steps) > 1:
            return "write_pending_plan"
        if len(write_steps) == 1:
            return "write_pending_action"
        return "read_plan"
    if decision.selected_tools:
        return "read_plan"
    return "direct_reply"


def _initial_validation(
    route_type: str,
    missing_fields: list[str],
) -> PlanValidationResult | None:
    if route_type != "clarification":
        return None
    return PlanValidationResult(
        status="blocked",
        safe_route_type="clarification",
        missing_fields=missing_fields,
        issues=[
            PlanIssue(
                code="missing_required_field",
                message=f"缺少必要字段：{', '.join(missing_fields)}",
                metadata={"missing_fields": missing_fields},
            )
        ]
        if missing_fields
        else [],
    )


def _steps_from_frames(frames: list[IntentFrame]) -> list[PlanStep]:
    steps: list[PlanStep] = []
    for frame in frames:
        if not frame.candidate_tools:
            continue
        steps.append(
            PlanStep(
                step_id=frame.intent,
                skill_name=_tool_name_for_frame(frame),
                params=_normalize_params(frame.params_hint or {}),
                risk=frame.risk,
                depends_on=list(frame.depends_on),
                evidence=dict(frame.planning_evidence or {}),
            )
        )
    return steps


def _tool_name_for_frame(frame: IntentFrame) -> str:
    if frame.intent == "create_worker":
        return "manage_workers"
    if frame.intent == "create_work_order":
        return "create_operation_work_order"
    return frame.candidate_tools[0]


def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(params)
    for key in ("workers", "unit_names"):
        if isinstance(normalized.get(key), list):
            normalized[key] = ",".join(str(item) for item in normalized[key])
    return normalized


def _merge_evidence(frames: list[IntentFrame]) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    for frame in frames:
        evidence.update(frame.planning_evidence or {})
    return evidence


def _collect_missing_fields(frames: list[IntentFrame]) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for frame in frames:
        for field in frame.missing_fields or []:
            if field in seen:
                continue
            fields.append(field)
            seen.add(field)
    return fields


__all__ = ["attach_validation", "plan_draft_from_router_decision"]
