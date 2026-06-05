"""pending action 文案与链式动作测试。"""

from app.infra.pending_actions import (
    build_confirm_message,
    build_confirmation_context,
    get_pending,
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
