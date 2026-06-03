"""pending action 文案与链式动作测试。"""

from app.infra.pending_actions import build_confirm_message, get_pending, store_pending


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
