import pytest

from app.skills.contracts import describe_contract_for_schema, validate_skill_args

pytestmark = pytest.mark.no_db


def test_manage_cost_create_record_requires_category():
    result = validate_skill_args(
        "manage_cost",
        {
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
        },
        candidates={"category": ["化肥", "种子", "农药", "人工", "其他"]},
    )

    assert result.valid is False
    assert result.missing_fields == ["category"]
    assert result.retryable is True
    assert result.message == "create_record 缺少必填字段：category"


@pytest.mark.parametrize(
    ("params", "missing_fields"),
    [
        (
            {"operation": "create_record", "category": "其他", "record_type": "cost"},
            ["amount"],
        ),
        ({"operation": "delete_record"}, ["record_id"]),
    ],
)
def test_manage_cost_write_operations_require_business_fields(
    params,
    missing_fields,
):
    result = validate_skill_args("manage_cost", params)

    assert result.valid is False
    assert result.missing_fields == missing_fields


@pytest.mark.parametrize(
    ("skill_name", "params", "missing_fields"),
    [
        ("manage_farm_logs", {"operation": "create_log"}, ["operation_type"]),
        (
            "manage_farm_logs",
            {"operation": "manage_log", "action": "update"},
            ["log_id"],
        ),
        ("manage_work_orders", {"operation": "create_work_order"}, ["operation_type"]),
        (
            "manage_work_orders",
            {"operation": "update_work_order"},
            ["work_order_id"],
        ),
        (
            "manage_workers",
            {"operation": "manage_worker", "action": "create"},
            ["name"],
        ),
        (
            "manage_workers",
            {"operation": "manage_worker", "action": "update"},
            ["worker_id"],
        ),
        (
            "manage_planting_units",
            {"operation": "manage_units", "action": "create"},
            ["cycle_id", "name"],
        ),
        (
            "manage_planting_units",
            {"operation": "manage_units", "action": "delete"},
            ["unit_id"],
        ),
        ("manage_cost_categories", {"operation": "create_category"}, ["name", "type"]),
        ("manage_cost_categories", {"operation": "delete_category"}, ["category_id"]),
        (
            "manage_labor_payment",
            {"operation": "manage_wage", "action": "save"},
            ["worker_name", "work_date", "cycle_id", "operation_type", "unit_price"],
        ),
        (
            "manage_labor_payment",
            {"operation": "manage_wage", "action": "update"},
            ["labor_entry_id"],
        ),
        (
            "manage_labor_payment",
            {"operation": "settle_payment"},
            ["scope"],
        ),
    ],
)
def test_write_operation_contracts_require_business_fields(
    skill_name,
    params,
    missing_fields,
):
    result = validate_skill_args(skill_name, params)

    assert result.valid is False
    assert result.missing_fields == missing_fields


@pytest.mark.parametrize(
    ("skill_name", "params", "missing_fields"),
    [
        (
            "manage_cost_categories",
            {"operation": "manage_category", "action": "delete"},
            ["category_id"],
        ),
        ("manage_cost_categories", {"action": "delete"}, ["category_id"]),
        ("manage_workers", {"action": "create"}, ["name"]),
        ("manage_workers", {"action": "update"}, ["worker_id"]),
        ("manage_planting_units", {"action": "create"}, ["cycle_id", "name"]),
        ("manage_planting_units", {"action": "delete"}, ["unit_id"]),
    ],
)
def test_contracts_resolve_compatible_action_only_write_calls(
    skill_name,
    params,
    missing_fields,
):
    result = validate_skill_args(skill_name, params)

    assert result.valid is False
    assert result.missing_fields == missing_fields


def test_contract_rejects_category_not_in_candidates():
    result = validate_skill_args(
        "manage_cost",
        {
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
            "category": "大棚膜",
        },
        candidates={"category": ["化肥", "种子", "农药", "人工", "其他"]},
    )

    assert result.valid is False
    assert result.invalid_candidates == {"category": "大棚膜 不在候选值中"}
    assert result.invalid_fields == {"category": "大棚膜 不在候选值中"}
    assert result.message == "category 无效：大棚膜 不在候选值中"


def test_contract_accepts_valid_create_record_args():
    result = validate_skill_args(
        "manage_cost",
        {
            "operation": "create_record",
            "amount": 5000,
            "record_type": "cost",
            "category": "其他",
        },
        candidates={"category": ["化肥", "种子", "农药", "人工", "其他"]},
    )

    assert result.valid is True
    assert result.missing_fields == []
    assert result.invalid_candidates == {}


def test_contract_accepts_manage_wage_save_with_worker_id():
    result = validate_skill_args(
        "manage_labor_payment",
        {
            "operation": "manage_wage",
            "action": "save",
            "worker_id": 12,
            "work_date": "2026-07-24",
            "cycle_id": 3,
            "operation_type": "采收",
            "unit_price": 200,
        },
    )

    assert result.valid is True


def test_contract_description_contains_create_record_required_fields():
    description = describe_contract_for_schema("manage_cost")

    assert "create_record 必填：amount, category" in description
