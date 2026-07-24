"""Pending 写工具参数契约校验。"""

from dataclasses import dataclass
from typing import Any

from app.skills.category_inference import infer_cost_category_from_text
from app.skills.candidates import load_skill_candidates
from app.skills.contracts import ContractValidationResult, validate_skill_args
from app.skills.metadata import (
    infer_skill_operation_name,
    resolve_skill_capability_metadata,
)


@dataclass(frozen=True)
class PendingToolArgValidation:
    """Runtime 层使用的契约校验结果。"""

    valid: bool
    skill_name: str
    contract_skill_name: str
    params: dict[str, Any]
    validation: ContractValidationResult
    message: str

    @property
    def missing_fields(self) -> list[str]:
        return list(self.validation.missing_fields)

    def trace_payload(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "skill_name": self.skill_name,
            "contract_skill_name": self.contract_skill_name,
            "missing_fields": list(self.validation.missing_fields),
            "invalid_candidates": dict(
                getattr(self.validation, "invalid_candidates", {})
                or getattr(self.validation, "invalid_fields", {})
                or {}
            ),
            "retryable": self.validation.retryable,
            "message": self.message,
            "contract_message": self.validation.message,
        }

    def to_trace_payload(self) -> dict[str, Any]:
        return self.trace_payload()


def validate_pending_tool_args(
    *,
    skill_name: str,
    params: dict[str, Any],
    farm_id: int,
    original_input: str = "",
) -> PendingToolArgValidation:
    """按 capability operation 契约校验 pending 写工具参数。"""
    normalized_params = dict(params or {})
    metadata = _resolve_contract_metadata(skill_name, normalized_params)
    contract_skill_name = str(metadata.get("capability") or skill_name)
    operation = metadata.get("operation")
    if not operation:
        operation = _infer_write_operation(contract_skill_name, normalized_params)
    if operation and normalized_params.get("operation") in (None, ""):
        normalized_params["operation"] = operation

    candidate_set = load_skill_candidates(farm_id)
    _repair_invalid_cost_category(
        contract_skill_name=contract_skill_name,
        params=normalized_params,
        candidates=candidate_set.values,
        original_input=original_input,
    )
    validation = validate_skill_args(
        contract_skill_name,
        normalized_params,
        candidates=candidate_set.values,
    )
    message = _contract_message(validation)
    return PendingToolArgValidation(
        valid=validation.valid,
        skill_name=skill_name,
        contract_skill_name=contract_skill_name,
        params=normalized_params,
        validation=validation,
        message=message,
    )


def validate_before_pending(
    skill_name: str,
    params: dict[str, Any],
    farm_id: int,
) -> PendingToolArgValidation:
    return validate_pending_tool_args(
        skill_name=skill_name,
        params=params,
        farm_id=farm_id,
    )


def _resolve_contract_metadata(
    skill_name: str, params: dict[str, Any]
) -> dict[str, Any]:
    operation = str(params.get("operation") or "").strip() or None
    return resolve_skill_capability_metadata(skill_name, operation) or {}


def _infer_write_operation(skill_name: str, params: dict[str, Any]) -> str | None:
    operation = infer_skill_operation_name(skill_name, params)
    if not operation:
        return None
    metadata = resolve_skill_capability_metadata(skill_name, operation) or {}
    if metadata.get("operation_risk") not in {"write_confirm", "write_high"}:
        return None
    return operation


def _repair_invalid_cost_category(
    *,
    contract_skill_name: str,
    params: dict[str, Any],
    candidates: dict[str, list[str]],
    original_input: str,
) -> None:
    if contract_skill_name != "manage_cost":
        return
    if params.get("operation") != "create_record":
        return
    category = str(params.get("category") or "").strip()
    if not category:
        return
    allowed = [str(item).strip() for item in candidates.get("category") or [] if item]
    if _candidate_allowed(category, allowed):
        return
    text = " ".join(
        str(value)
        for value in (
            category,
            params.get("note"),
            params.get("description"),
            original_input,
        )
        if value not in (None, "")
    )
    inferred = infer_cost_category_from_text(
        allowed,
        text,
        allow_fallback_other=False,
    )
    if inferred is None:
        return
    params["category"] = inferred[0]
    params["_category_repair_strategy"] = inferred[1]


def _candidate_allowed(value: str, allowed_values: list[str]) -> bool:
    for allowed in allowed_values:
        if value == allowed:
            return True
        if ":" in allowed and value in allowed.split(":", maxsplit=1):
            return True
    return False


def _contract_message(validation: ContractValidationResult) -> str:
    if validation.valid:
        return ""
    message = validation.message or "参数不完整，暂不能创建待确认操作。"
    return f"{message}，请补充后我再为你确认。"
