"""Pending action/plan trace payload helpers."""

from __future__ import annotations

from typing import Any

from app.infra.pending_actions import PendingPlanStep


_SENSITIVE_TRACE_KEYS = {
    "api_key",
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
}


def pending_steps_trace_payload(
    pending_steps: list[PendingPlanStep],
) -> list[dict[str, Any]]:
    return [
        {
            "step_id": step.step_id,
            "step_index": step.step_index,
            "tool_name": step.tool_name,
            "params": redact_trace_payload(step.params),
            "depends_on": list(step.depends_on),
        }
        for step in pending_steps
    ]


def tool_calls_trace_payload(tool_calls: list[dict]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(tool_call.get("id") or ""),
            "name": str(tool_call.get("name") or ""),
            "args": redact_trace_payload(dict(tool_call.get("args") or {})),
        }
        for tool_call in tool_calls
    ]


def redact_trace_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if _is_sensitive_trace_key(key)
            else redact_trace_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_trace_payload(item) for item in value]
    return value


def pending_plan_contract_diagnostics(
    *,
    blocked_steps: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "param_source_diffs": [
            diff
            for blocked_step in blocked_steps
            if (
                diff := _pending_step_tool_call_diff(
                    blocked_step=blocked_step,
                    tool_calls=tool_calls,
                )
            )
        ]
    }


def blocked_missing_fields(blocked_steps: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for step in blocked_steps:
        validation = step.get("contract_validation")
        if not isinstance(validation, dict):
            continue
        for field in validation.get("missing_fields") or []:
            field_name = str(field)
            if field_name in seen:
                continue
            fields.append(field_name)
            seen.add(field_name)
    return fields


def first_param_source_diagnosis(diagnostics: dict[str, Any]) -> str | None:
    diffs = diagnostics.get("param_source_diffs")
    if not isinstance(diffs, list) or not diffs:
        return None
    first = diffs[0]
    if not isinstance(first, dict):
        return None
    diagnosis = first.get("diagnosis")
    return str(diagnosis) if diagnosis else None


def pending_plan_contract_error_message(blocked: list[dict[str, Any]]) -> str:
    details = "; ".join(
        f"{item['step_id']} {item['tool_name']}: {item['message']}" for item in blocked
    )
    return f"pending plan contract blocked: {details}"


def _pending_step_tool_call_diff(
    *,
    blocked_step: dict[str, Any],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any] | None:
    tool_name = str(blocked_step.get("tool_name") or "")
    related_calls = [call for call in tool_calls if call.get("name") == tool_name]
    if not related_calls:
        return None

    validation = blocked_step.get("contract_validation")
    missing_fields = []
    if isinstance(validation, dict):
        missing_fields = [
            str(field) for field in validation.get("missing_fields") or []
        ]

    fields_present_in_tool_calls: dict[str, list[str]] = {}
    for field in missing_fields:
        call_ids = [
            str(call.get("id") or "")
            for call in related_calls
            if _trace_args_has_field(call.get("args"), field)
        ]
        if call_ids:
            fields_present_in_tool_calls[field] = call_ids

    if not fields_present_in_tool_calls:
        return {
            "step_id": blocked_step.get("step_id"),
            "tool_name": tool_name,
            "related_tool_call_ids": [call["id"] for call in related_calls],
            "missing_fields": missing_fields,
            "diagnosis": "pending_step_and_tool_calls_missing_required_fields",
        }

    return {
        "step_id": blocked_step.get("step_id"),
        "tool_name": tool_name,
        "related_tool_call_ids": [call["id"] for call in related_calls],
        "missing_fields": missing_fields,
        "fields_present_in_tool_calls": fields_present_in_tool_calls,
        "diagnosis": "pending_step_missing_field_present_in_llm_tool_call",
    }


def _trace_args_has_field(args: Any, field: str) -> bool:
    if not isinstance(args, dict):
        return False
    value = args.get(field)
    return value is not None and value != ""


def _is_sensitive_trace_key(key: Any) -> bool:
    return str(key).strip().lower() in _SENSITIVE_TRACE_KEYS


__all__ = [
    "blocked_missing_fields",
    "first_param_source_diagnosis",
    "pending_plan_contract_diagnostics",
    "pending_plan_contract_error_message",
    "pending_steps_trace_payload",
    "redact_trace_payload",
    "tool_calls_trace_payload",
]
