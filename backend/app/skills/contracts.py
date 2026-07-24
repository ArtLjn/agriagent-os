"""Operation 级 function call 参数契约。"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OperationContract:
    required_fields: tuple[str, ...] = ()
    candidate_fields: tuple[str, ...] = ()
    default_fields: dict[str, Any] = field(default_factory=dict)
    repairable_missing_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillFunctionContract:
    operations: dict[str, OperationContract]


@dataclass(frozen=True)
class ContractValidationResult:
    valid: bool
    missing_fields: list[str] = field(default_factory=list)
    invalid_candidates: dict[str, str] = field(default_factory=dict)
    retryable: bool = False
    message: str = ""

    @property
    def invalid_fields(self) -> dict[str, str]:
        return self.invalid_candidates


_CONTRACTS: dict[str, SkillFunctionContract] = {
    "manage_cost": SkillFunctionContract(
        operations={
            "create_record": OperationContract(
                required_fields=("amount", "category"),
                candidate_fields=("category",),
                default_fields={"record_date": "today", "record_type": "cost"},
                repairable_missing_fields=("amount", "category", "record_type"),
            ),
            "delete_record": OperationContract(required_fields=("record_id",)),
            "settle_debt": OperationContract(
                required_fields=("counterparty",),
                repairable_missing_fields=("counterparty",),
            ),
        }
    ),
    "manage_farm_logs": SkillFunctionContract(
        operations={
            "create_log": OperationContract(
                required_fields=("operation_type",),
                default_fields={"operation_date": "today"},
                repairable_missing_fields=("operation_type",),
            ),
            "manage_log": OperationContract(required_fields=("log_id",)),
        }
    ),
    "manage_work_orders": SkillFunctionContract(
        operations={
            "create_work_order": OperationContract(
                required_fields=("operation_type",),
                default_fields={"operation_date": "today"},
                repairable_missing_fields=("operation_type", "cycle_id", "unit_names"),
            ),
            "update_work_order": OperationContract(required_fields=("work_order_id",)),
        }
    ),
    "manage_workers": SkillFunctionContract(
        operations={
            "manage_worker": OperationContract(
                candidate_fields=("worker_id",),
                repairable_missing_fields=("worker_id", "name"),
            ),
        }
    ),
    "manage_planting_units": SkillFunctionContract(
        operations={
            "manage_units": OperationContract(
                repairable_missing_fields=("cycle_id", "name", "unit_id"),
            ),
        }
    ),
    "manage_cost_categories": SkillFunctionContract(
        operations={
            "create_category": OperationContract(
                required_fields=("name", "type"),
                candidate_fields=("type",),
                repairable_missing_fields=("name", "type"),
            ),
            "delete_category": OperationContract(required_fields=("category_id",)),
        }
    ),
    "manage_labor_payment": SkillFunctionContract(
        operations={
            "settle_payment": OperationContract(
                required_fields=("scope",),
                repairable_missing_fields=("scope", "worker", "worker_name"),
            ),
            "manage_wage": OperationContract(
                repairable_missing_fields=(
                    "worker_name",
                    "work_date",
                    "cycle_id",
                    "operation_type",
                    "unit_price",
                    "labor_entry_id",
                ),
            ),
        }
    ),
}


def get_skill_contract(skill_name: str) -> SkillFunctionContract | None:
    return _CONTRACTS.get(_normalize_skill_name(skill_name))


def get_operation_contract(
    skill_name: str,
    operation: str | None,
) -> OperationContract | None:
    operation_name = _clean(operation)
    if not operation_name:
        return None
    contract = get_skill_contract(skill_name)
    if contract is None:
        return None
    return contract.operations.get(operation_name)


def validate_skill_args(
    skill_name: str,
    args: dict[str, Any],
    candidates: dict[str, list[str]] | None = None,
) -> ContractValidationResult:
    normalized_skill_name = _normalize_skill_name(skill_name)
    params = dict(args or {})
    operation = _resolve_operation(normalized_skill_name, params)
    operation_contract = get_operation_contract(normalized_skill_name, operation)
    if operation_contract is None:
        return ContractValidationResult(valid=True)

    required_fields = operation_contract.required_fields + _action_required_fields(
        normalized_skill_name, params
    )
    missing = [field for field in required_fields if params.get(field) in (None, "")]
    invalid = _invalid_candidate_fields(
        params=params,
        candidate_fields=operation_contract.candidate_fields,
        candidates=candidates or {},
    )
    if not missing and not invalid:
        return ContractValidationResult(valid=True)

    retryable = any(
        field in operation_contract.repairable_missing_fields for field in missing
    )
    return ContractValidationResult(
        valid=False,
        missing_fields=missing,
        invalid_candidates=invalid,
        retryable=retryable,
        message=_validation_message(operation or "", missing, invalid),
    )


def describe_contract_for_schema(skill_name: str) -> str:
    contract = get_skill_contract(skill_name)
    if contract is None:
        return ""

    operation_parts = []
    normalized = _normalize_skill_name(skill_name)
    for operation, operation_contract in contract.operations.items():
        required = (
            operation_contract.required_fields
            + _describe_action_required_fields(normalized, operation)
        )
        if not required:
            continue
        operation_parts.append(f"{operation} 必填：{', '.join(required)}")
    if not operation_parts:
        return ""
    return "参数契约：" + "；".join(operation_parts) + "。"


def _action_required_fields(skill_name: str, params: dict[str, Any]) -> tuple[str, ...]:
    operation = _resolve_operation(skill_name, params)
    action = _clean(params.get("action"))
    if skill_name == "manage_workers" and operation == "manage_worker":
        if action in {"update", "deactivate", "restore"}:
            return ("worker_id",)
        if action == "create":
            return ("name",)
    if skill_name == "manage_planting_units" and operation == "manage_units":
        if action == "create":
            return ("cycle_id", "name")
        if action in {"update", "delete"}:
            return ("unit_id",)
    if skill_name == "manage_labor_payment" and operation == "manage_wage":
        if action == "update":
            return ("labor_entry_id",)
        if action in {"", "save"}:
            worker_field = (
                ()
                if _has_any(params, ("worker_id", "worker_name", "worker"))
                else ("worker_name",)
            )
            return worker_field + (
                "work_date",
                "cycle_id",
                "operation_type",
                "unit_price",
            )
    return ()


def _has_any(params: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(params.get(field) not in (None, "") for field in fields)


def _resolve_operation(skill_name: str, params: dict[str, Any]) -> str:
    operation = _clean(params.get("operation"))
    action = _clean(params.get("action"))
    if skill_name == "manage_cost_categories":
        if operation == "manage_category":
            operation = ""
        if not operation and action == "delete":
            return "delete_category"
        if not operation and action in {"", "create"}:
            return "create_category"
    if skill_name == "manage_workers" and not operation:
        if action in {"create", "update", "deactivate", "restore"}:
            return "manage_worker"
    if skill_name == "manage_planting_units" and not operation:
        if action in {"create", "update", "delete"}:
            return "manage_units"
    return operation


def _describe_action_required_fields(
    skill_name: str,
    operation: str,
) -> tuple[str, ...]:
    if skill_name == "manage_workers" and operation == "manage_worker":
        return ("create:name", "update/deactivate/restore:worker_id")
    if skill_name == "manage_planting_units" and operation == "manage_units":
        return ("create:cycle_id/name", "update/delete:unit_id")
    if skill_name == "manage_labor_payment" and operation == "manage_wage":
        return (
            "save:worker_name/work_date/cycle_id/operation_type/unit_price",
            "update:labor_entry_id",
        )
    return ()


def _invalid_candidate_fields(
    *,
    params: dict[str, Any],
    candidate_fields: tuple[str, ...],
    candidates: dict[str, list[str]],
) -> dict[str, str]:
    invalid = {}
    for field_name in candidate_fields:
        if field_name not in candidates:
            continue
        allowed_values = candidates.get(field_name) or []
        value = params.get(field_name)
        if value in (None, "") or not allowed_values:
            continue
        disallowed = [
            item
            for item in _candidate_input_values(value)
            if not _candidate_value_allowed(item, allowed_values)
        ]
        if disallowed:
            invalid[field_name] = f"{', '.join(disallowed)} 不在候选值中"
    return invalid


def _candidate_input_values(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    if "," in text or "，" in text:
        return [
            part.strip() for part in text.replace("，", ",").split(",") if part.strip()
        ]
    return [text]


def _candidate_value_allowed(value: str, allowed_values: list[str]) -> bool:
    for allowed in allowed_values:
        text = str(allowed).strip()
        if value == text:
            return True
        if ":" in text and value in text.split(":", maxsplit=1):
            return True
    return False


def _validation_message(
    operation: str,
    missing_fields: list[str],
    invalid_candidates: dict[str, str],
) -> str:
    parts = []
    if missing_fields:
        parts.append(f"{operation} 缺少必填字段：{', '.join(missing_fields)}")
    for field_name, reason in invalid_candidates.items():
        parts.append(f"{field_name} 无效：{reason}")
    return "；".join(parts)


def _normalize_skill_name(skill_name: str) -> str:
    return str(skill_name or "").strip().replace("-", "_")


def _clean(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()
