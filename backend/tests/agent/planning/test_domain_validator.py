"""PlanDraft Domain Validator 回归测试。"""

import pytest

from app.agent.runtime.planning.models import (
    InferredField,
    PlanDraft,
    PlanStep,
    RouteType,
)
from app.agent.runtime.planning.validator import DomainValidator, WorkerDefaultWage

pytestmark = pytest.mark.no_db


def test_direct_reply_passes_without_steps() -> None:
    draft = PlanDraft(
        turn_id="turn-1",
        session_id="session-1",
        farm_id=1,
        raw_user_input="你好",
        route_type="direct_reply",
    )

    result = DomainValidator().validate(draft)

    assert result.is_valid is True
    assert result.safe_route_type == "direct_reply"
    assert result.missing_fields == []
    assert result.issues == []


def test_read_plan_passes_with_read_step() -> None:
    draft = PlanDraft(
        turn_id="turn-2",
        session_id="session-1",
        farm_id=1,
        raw_user_input="我的工人有哪些",
        route_type="read_plan",
        steps=[
            PlanStep(
                step_id="step-1",
                skill_name="get_workers",
                params={},
                risk="read",
            )
        ],
    )

    result = DomainValidator().validate(draft)

    assert result.is_valid is True
    assert result.safe_route_type == "read_plan"
    assert result.missing_fields == []


def test_single_write_rejects_empty_params_before_pending_creation() -> None:
    draft = PlanDraft(
        turn_id="turn-3",
        session_id="session-1",
        farm_id=1,
        raw_user_input="今天李海去6号棚压蔓",
        route_type="write_pending_action",
        steps=[
            PlanStep(
                step_id="step-1",
                skill_name="create_operation_work_order",
                params={},
                risk="write_confirm",
            )
        ],
    )

    result = DomainValidator().validate(draft)

    assert result.is_valid is False
    assert result.safe_route_type == "clarification"
    assert "steps[0].params" in result.missing_fields
    assert result.issues[0].code == "empty_write_params"


def test_single_write_missing_operation_type_becomes_clarification() -> None:
    draft = PlanDraft(
        turn_id="turn-4",
        session_id="session-1",
        farm_id=1,
        raw_user_input="李海这个月干了15天",
        route_type="write_pending_action",
        steps=[
            PlanStep(
                step_id="step-1",
                skill_name="create_operation_work_order",
                params={"workers": "李海", "quantity": 15},
                risk="write_confirm",
            )
        ],
    )

    result = DomainValidator().validate(draft)

    assert result.is_valid is False
    assert result.safe_route_type == "clarification"
    assert result.missing_fields == ["operation_type"]
    assert result.issues[0].code == "missing_required_field"


def test_uniquely_inferable_worker_default_wage_is_recorded() -> None:
    def lookup_worker_default_wage(worker_name: str) -> list[WorkerDefaultWage]:
        assert worker_name == "李海"
        return [
            WorkerDefaultWage(
                worker_id=7,
                worker_name="李海",
                pay_type="daily",
                unit_price=120,
                source="worker_profile",
            )
        ]

    draft = PlanDraft(
        turn_id="turn-5",
        session_id="session-1",
        farm_id=1,
        raw_user_input="李海这个月压瓜15天",
        route_type="write_pending_action",
        steps=[
            PlanStep(
                step_id="step-1",
                skill_name="create_operation_work_order",
                params={
                    "operation_type": "压瓜",
                    "workers": "李海",
                    "quantity": 15,
                },
                risk="write_confirm",
            )
        ],
    )

    result = DomainValidator(
        lookup_worker_default_wage=lookup_worker_default_wage
    ).validate(draft)

    assert result.is_valid is True
    assert result.safe_route_type == "write_pending_action"
    assert result.missing_fields == []
    assert result.inferred_fields == [
        InferredField(
            field_path="steps[0].params.unit_price",
            value=120,
            source="worker_profile",
            confidence=1.0,
            metadata={
                "worker_id": 7,
                "worker_name": "李海",
                "pay_type": "daily",
            },
        )
    ]


def test_ambiguous_worker_default_wage_becomes_clarification() -> None:
    def lookup_worker_default_wage(_worker_name: str) -> list[WorkerDefaultWage]:
        return [
            WorkerDefaultWage(
                worker_id=7,
                worker_name="李海",
                pay_type="daily",
                unit_price=120,
                source="worker_profile",
            ),
            WorkerDefaultWage(
                worker_id=9,
                worker_name="李海",
                pay_type="daily",
                unit_price=140,
                source="worker_profile",
            ),
        ]

    draft = PlanDraft(
        turn_id="turn-6",
        session_id="session-1",
        farm_id=1,
        raw_user_input="李海这个月压瓜15天",
        route_type="write_pending_action",
        steps=[
            PlanStep(
                step_id="step-1",
                skill_name="create_operation_work_order",
                params={
                    "operation_type": "压瓜",
                    "workers": "李海",
                    "quantity": 15,
                },
                risk="write_confirm",
            )
        ],
    )

    result = DomainValidator(
        lookup_worker_default_wage=lookup_worker_default_wage
    ).validate(draft)

    assert result.is_valid is False
    assert result.safe_route_type == "clarification"
    assert result.missing_fields == ["unit_price"]
    assert result.issues[0].code == "ambiguous_worker_default_wage"


def test_multi_step_write_passes_when_each_step_is_valid() -> None:
    draft = PlanDraft(
        turn_id="turn-7",
        session_id="session-1",
        farm_id=1,
        raw_user_input="新来一个工人李丽工资100一天，今天去6号棚收水稻",
        route_type="write_pending_plan",
        steps=[
            PlanStep(
                step_id="step-1",
                skill_name="manage_workers",
                params={
                    "action": "create",
                    "name": "李丽",
                    "default_pay_type": "daily",
                    "default_unit_price": 100,
                },
                risk="write_confirm",
            ),
            PlanStep(
                step_id="step-2",
                skill_name="create_operation_work_order",
                params={
                    "operation_type": "收水稻",
                    "unit_names": "6号棚",
                    "workers": "李丽",
                    "unit_price": 100,
                    "quantity": 1,
                },
                risk="write_confirm",
                depends_on=["step-1"],
            ),
        ],
    )

    result = DomainValidator().validate(draft)

    assert result.is_valid is True
    assert result.safe_route_type == "write_pending_plan"
    assert result.missing_fields == []
    assert result.inferred_fields == []


def test_route_type_literals_cover_plan_draft_contract() -> None:
    route_types: set[RouteType] = {
        "direct_reply",
        "read_plan",
        "write_pending_action",
        "write_pending_plan",
        "clarification",
    }

    assert len(route_types) == 5
