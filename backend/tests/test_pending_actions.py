"""pending action 文案、生命周期与链式动作测试。"""

from unittest.mock import patch

from app.infra.pending_actions import (
    WRITE_SKILLS,
    build_confirm_message,
    build_confirmation_context,
    get_pending,
    get_cache_groups_for_skill,
    remove_pending,
    store_pending,
)


def test_confirm_message_hides_internal_param_keys():
    message = build_confirm_message(
        "create_crop_template",
        {"crop_name": "小麦"},
        original_input="我想种小麦",
    )

    assert "crop_name" not in message
    assert "参数：" not in message
    assert "小麦" in message
    assert "理解：" in message


def test_confirm_message_includes_debt_fields_for_cost_record():
    message = build_confirm_message(
        "create_cost_record",
        {
            "category": "种子",
            "amount": 130,
            "record_type": "cost",
            "record_subtype": "赊账",
            "counterparty": "张三",
        },
    )

    first_line = message.splitlines()[0]
    assert "确认记账" in first_line
    assert "种子" in message
    assert "130元" in message
    assert "赊账" in first_line
    assert "张三" in first_line


def test_write_skill_registry_covers_runtime_write_skills():
    expected = {
        "create_cost_record",
        "create_crop_cycle",
        "manage_crop_cycle",
        "create_crop_template",
        "create_operation_work_order",
        "settle_debt",
        "settle_labor_payment",
        "update_crop_cycle",
        "update_operation_work_order",
        "manage_workers",
        "manage_wages",
        "delete_cost_record",
        "manage_cost_categories",
        "manage_planting_units",
        "manage_crop_templates",
        "manage_farm_logs",
        "delete_crop_cycle",
        "manage_user_settings",
    }

    assert WRITE_SKILLS == expected
    assert get_cache_groups_for_skill("settle_labor_payment") == [
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ]
    assert get_cache_groups_for_skill("update_crop_cycle") == [
        "crop_cycle",
        "get_farm_status",
    ]
    assert get_cache_groups_for_skill("update_crop_stage") == [
        "crop_cycle",
        "get_farm_status",
    ]
    assert get_cache_groups_for_skill("update_operation_work_order") == [
        "farm_logs",
        "cost_analytics",
        "cost_summary",
        "get_farm_status",
    ]


def test_store_pending_keeps_follow_up_action():
    store_pending(
        1,
        "create_crop_template",
        {"crop_name": "小麦"},
        follow_up_skill_name="create_crop_cycle",
        follow_up_params={"crop_name": "小麦"},
        follow_up_original_input="我想种小麦",
    )

    pending = get_pending(1)

    assert pending is not None
    assert pending.follow_up_skill_name == "create_crop_cycle"
    assert pending.follow_up_params == {"crop_name": "小麦"}
    assert pending.follow_up_original_input == "我想种小麦"


def test_pending_action_times_out_after_ttl():
    with patch("app.infra.pending_actions.time.time", return_value=1_000):
        store_pending(1, "create_cost_record", {"amount": 100})

    with patch("app.infra.pending_actions.time.time", return_value=1_301):
        pending = get_pending(1)

    assert pending is None


def test_store_pending_overwrites_existing_action_for_same_farm():
    first_id = store_pending(1, "create_cost_record", {"amount": 100})
    second_id = store_pending(1, "update_crop_cycle", {"start_date": "2026-09-01"})

    pending = get_pending(1)

    assert pending is not None
    assert pending.action_id == second_id
    assert pending.action_id != first_id
    assert pending.skill_name == "update_crop_cycle"
    assert pending.params == {"start_date": "2026-09-01"}


def test_pending_actions_are_scoped_by_session_id():
    remove_pending(1)
    store_pending(
        1,
        "create_crop_cycle",
        {"crop_name": "韭菜"},
        session_id="session-a",
    )

    assert get_pending(1, session_id="session-a") is not None
    assert get_pending(1, session_id="session-b") is None
    assert get_pending(1) is None

    remove_pending(1, session_id="session-a")


def test_build_confirmation_context_for_crop_cycle_update():
    context = build_confirmation_context(
        "update_crop_cycle",
        {
            "cycle_id": 9,
            "cycle_name": "夏季玉米",
            "start_date": "2026-09-01",
            "old_start_date": "2026-06-05",
            "crop_name": "玉米",
        },
        original_input="修改玉米茬口9月1开始",
    )

    assert context["skill_name"] == "update_crop_cycle"
    assert context["original_input"] == "修改玉米茬口9月1开始"
    assert context["target"] == {
        "type": "crop_cycle",
        "id": 9,
        "name": "夏季玉米",
    }
    assert context["changes"][0]["field"] == "start_date"
    assert context["changes"][0]["label"] == "开始日期"
    assert context["changes"][0]["old"] == "2026-06-05"
    assert context["changes"][0]["new"] == "2026-09-01"
    assert context["inferred_fields"] == {
        "crop_name": "玉米",
        "start_date": "2026-09-01",
    }
    assert context["risk_notes"] == []
    assert "start_date" in context["editable_fields"]


def test_confirm_message_includes_crop_cycle_date_diff():
    message = build_confirm_message(
        "update_crop_cycle",
        {
            "cycle_id": 9,
            "cycle_name": "夏季玉米",
            "start_date": "2026-09-01",
            "old_start_date": "2026-06-05",
            "crop_name": "玉米",
        },
        original_input="修改玉米茬口9月1开始",
    )

    assert "夏季玉米" in message
    assert "2026-06-05" in message
    assert "2026-09-01" in message
    assert "修改玉米茬口9月1开始" in message


def test_build_confirmation_context_for_operation_work_order_labor_details():
    context = build_confirmation_context(
        "create_operation_work_order",
        {
            "operation_type": "人工授粉",
            "operation_date": "2026-06-05",
            "cycle_id": 9,
            "cycle_name": "夏季玉米",
            "unit_names": "东棚1号",
            "workers": "老王,老李",
            "unit_price": 200,
            "paid_worker": "老王",
            "paid_amount": 200,
        },
        original_input="今天东棚授粉，老王老李各200，先付老王",
    )

    assert context["target"]["type"] == "operation_work_order"
    assert context["target"]["operation_type"] == "人工授粉"
    assert context["target"]["operation_date"] == "2026-06-05"
    assert context["target"]["cycle_id"] == 9
    assert context["scope"]["scope_type"] == "unit"
    assert context["scope"]["units"] == ["东棚1号"]
    labor = context["labor"]
    assert labor["workers"] == ["老王", "老李"]
    assert labor["payable_amount"] == "400.00"
    assert labor["paid_amount"] == "200.00"
    assert labor["unpaid_amount"] == "200.00"
    assert context["inferred_fields"]["cycle_id"] == 9
    assert "workers" in context["editable_fields"]
    assert context["risk_notes"]


def test_confirm_message_includes_operation_work_order_payment_summary():
    message = build_confirm_message(
        "create_operation_work_order",
        {
            "operation_type": "人工授粉",
            "operation_date": "2026-06-05",
            "unit_names": "东棚1号",
            "workers": ["老王", "老李"],
            "unit_price": 200,
            "paid_amount": 200,
        },
        original_input="今天东棚授粉，老王老李各200，先付200",
    )

    assert "确认创建农事作业单：人工授粉" in message
    assert "日期：2026-06-05" in message
    assert "范围：东棚1号" in message
    assert "人工：老王、老李" in message
    assert "应付400.00元" in message
    assert "已付200.00元" in message
    assert "未付200.00元" in message


def test_store_pending_keeps_confirmation_context():
    confirmation_context = {
        "skill_name": "update_crop_cycle",
        "target": {"type": "crop_cycle", "id": 9, "name": "夏季玉米"},
    }

    store_pending(
        2,
        "update_crop_cycle",
        {"cycle_id": 9, "start_date": "2026-09-01"},
        confirmation_context=confirmation_context,
    )

    pending = get_pending(2)

    assert pending is not None
    assert pending.confirmation_context == confirmation_context
