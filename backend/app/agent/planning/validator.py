"""PlanDraft Domain Validator。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent.planning.models import (
    InferredField,
    PlanDraft,
    PlanIssue,
    PlanStep,
    PlanValidationResult,
    RouteType,
)


@dataclass(frozen=True)
class WorkerDefaultWage:
    """可由外部上下文解析出的工人默认工资。"""

    worker_id: int | None
    worker_name: str
    pay_type: str
    unit_price: float | int
    source: str = "worker_profile"


WorkerDefaultWageLookup = Callable[[str], list[WorkerDefaultWage]]


class DomainValidator:
    """集中验证 PlanDraft 的跨 Skill 领域完整性。"""

    def __init__(
        self,
        *,
        lookup_worker_default_wage: WorkerDefaultWageLookup | None = None,
    ) -> None:
        self._lookup_worker_default_wage = lookup_worker_default_wage

    def validate(self, draft: PlanDraft) -> PlanValidationResult:
        """验证草稿并返回安全路由结果。"""
        missing_fields = list(draft.missing_fields)
        inferred_fields: list[InferredField] = []
        issues: list[PlanIssue] = []

        if draft.route_type in {"direct_reply", "read_plan", "clarification"}:
            return self._result(
                route_type=draft.route_type,
                missing_fields=missing_fields,
                inferred_fields=inferred_fields,
                issues=issues,
            )

        for index, step in enumerate(draft.steps):
            self._validate_write_step(
                step=step,
                index=index,
                missing_fields=missing_fields,
                inferred_fields=inferred_fields,
                issues=issues,
            )

        return self._result(
            route_type=draft.route_type,
            missing_fields=missing_fields,
            inferred_fields=inferred_fields,
            issues=issues,
        )

    def _validate_write_step(
        self,
        *,
        step: PlanStep,
        index: int,
        missing_fields: list[str],
        inferred_fields: list[InferredField],
        issues: list[PlanIssue],
    ) -> None:
        if not step.params:
            field_path = f"steps[{index}].params"
            self._add_missing(missing_fields, field_path)
            issues.append(
                PlanIssue(
                    code="empty_write_params",
                    message="写入步骤缺少参数，不能创建待确认写操作。",
                    field_path=field_path,
                )
            )
            return

        required_fields = self._required_fields_for_step(step)
        has_missing_required = False
        for field_name in required_fields:
            if self._is_empty(step.params.get(field_name)):
                has_missing_required = True
                self._add_missing(missing_fields, field_name)
                issues.append(
                    PlanIssue(
                        code="missing_required_field",
                        message=f"写入步骤缺少必填字段 {field_name}。",
                        field_path=f"steps[{index}].params.{field_name}",
                        metadata={"skill_name": step.skill_name},
                    )
                )

        if step.skill_name == "create_operation_work_order" and not has_missing_required:
            self._validate_operation_wage(
                step=step,
                index=index,
                missing_fields=missing_fields,
                inferred_fields=inferred_fields,
                issues=issues,
            )

    def _validate_operation_wage(
        self,
        *,
        step: PlanStep,
        index: int,
        missing_fields: list[str],
        inferred_fields: list[InferredField],
        issues: list[PlanIssue],
    ) -> None:
        if self._has_wage_policy(step.params):
            return

        worker_name = self._single_worker_name(step.params.get("workers"))
        if not worker_name:
            return

        if self._lookup_worker_default_wage is None:
            self._add_missing(missing_fields, "unit_price")
            issues.append(
                PlanIssue(
                    code="missing_worker_default_wage",
                    message="涉及工人工资但缺少本次单价，且没有可用的默认工资来源。",
                    field_path=f"steps[{index}].params.unit_price",
                    metadata={"worker_name": worker_name},
                )
            )
            return

        matches = self._lookup_worker_default_wage(worker_name)
        if len(matches) == 1:
            wage = matches[0]
            inferred_fields.append(
                InferredField(
                    field_path=f"steps[{index}].params.unit_price",
                    value=wage.unit_price,
                    source=wage.source,
                    confidence=1.0,
                    metadata={
                        "worker_id": wage.worker_id,
                        "worker_name": wage.worker_name,
                        "pay_type": wage.pay_type,
                    },
                )
            )
            return

        self._add_missing(missing_fields, "unit_price")
        issue_code = (
            "ambiguous_worker_default_wage"
            if len(matches) > 1
            else "missing_worker_default_wage"
        )
        issues.append(
            PlanIssue(
                code=issue_code,
                message="工人默认工资无法唯一确定，需要用户确认本次工资。",
                field_path=f"steps[{index}].params.unit_price",
                metadata={
                    "worker_name": worker_name,
                    "candidate_count": len(matches),
                },
            )
        )

    def _required_fields_for_step(self, step: PlanStep) -> tuple[str, ...]:
        if step.skill_name == "create_operation_work_order":
            return ("operation_type",)
        if step.skill_name == "manage_workers":
            return ("action",)
        return ()

    def _result(
        self,
        *,
        route_type: RouteType,
        missing_fields: list[str],
        inferred_fields: list[InferredField],
        issues: list[PlanIssue],
    ) -> PlanValidationResult:
        status = "blocked" if any(issue.blocking for issue in issues) else "valid"
        safe_route_type: RouteType = "clarification" if status == "blocked" else route_type
        return PlanValidationResult(
            status=status,
            safe_route_type=safe_route_type,
            missing_fields=missing_fields,
            inferred_fields=inferred_fields,
            issues=issues,
        )

    def _has_wage_policy(self, params: dict[str, Any]) -> bool:
        if not self._is_empty(params.get("unit_price")):
            return True
        if params.get("no_wage") is True:
            return True
        wage_policy = params.get("wage_policy")
        return isinstance(wage_policy, str) and wage_policy.strip().lower() in {
            "none",
            "no_wage",
            "free",
        }

    def _single_worker_name(self, value: Any) -> str | None:
        if isinstance(value, str):
            names = [item.strip() for item in value.split(",") if item.strip()]
            return names[0] if len(names) == 1 else None
        if isinstance(value, list):
            names = [str(item).strip() for item in value if str(item).strip()]
            return names[0] if len(names) == 1 else None
        return None

    def _add_missing(self, missing_fields: list[str], field_name: str) -> None:
        if field_name not in missing_fields:
            missing_fields.append(field_name)

    def _is_empty(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip()
        if isinstance(value, (list, tuple, dict, set)):
            return len(value) == 0
        return False
