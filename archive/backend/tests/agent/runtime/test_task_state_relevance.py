"""TaskState 早期相关性判断测试。"""

import pytest

from app.agent.runtime.task_state_relevance import evaluate_task_state_relevance

pytestmark = pytest.mark.no_db


def _active_task(
    *,
    task_type: str = "planting_plan",
    missing_information: list[str] | None = None,
) -> dict:
    return {
        "task_id": "task-1",
        "task_type": task_type,
        "goal": "帮我规划种植",
        "status": "waiting_user",
        "entities": {"crop": "玉米"},
        "missing_information": missing_information or [],
        "next_action": "等待用户补充信息",
    }


def test_relevance_injects_area_followup_for_planting_plan() -> None:
    decision = evaluate_task_state_relevance(
        "20亩",
        _active_task(missing_information=["种植面积"]),
    )

    assert decision.should_inject is True
    assert decision.decision == "inject"
    assert decision.score >= 0.75


def test_relevance_prioritizes_missing_slot_over_bypass_keyword() -> None:
    decision = evaluate_task_state_relevance(
        "设置成20亩",
        _active_task(missing_information=["种植面积"]),
    )

    assert decision.should_inject is True
    assert decision.decision == "inject"
    assert decision.score >= 0.75


def test_relevance_injects_continuation_short_inputs() -> None:
    for user_input in [
        "继续",
        "确认",
        "确认。",
        "确认创建",
        "你好，确认",
        "可以，按刚才的方案创建",
        "天气好的话按刚才方案创建",
    ]:
        decision = evaluate_task_state_relevance(
            user_input,
            _active_task(
                task_type="crop_cycle_setup",
                missing_information=[],
            ),
        )

        assert decision.should_inject is True
        assert decision.decision == "inject"
        assert decision.score >= 0.75


def test_relevance_injects_confirmation_when_waiting_next_action() -> None:
    decision = evaluate_task_state_relevance(
        "确认执行",
        {
            **_active_task(
                task_type="crop_cycle_setup",
                missing_information=[],
            ),
            "next_action": "等待用户确认创建茬口",
        },
    )

    assert decision.should_inject is True
    assert decision.decision == "inject"


def test_relevance_injects_crop_cycle_setup_write_continuation() -> None:
    decision = evaluate_task_state_relevance(
        "创建茬口创建模版创建地块",
        _active_task(
            task_type="crop_cycle_setup",
            missing_information=["种植单元名称"],
        ),
    )

    assert decision.should_inject is True
    assert decision.decision == "inject"
    assert decision.score >= 0.75


def test_relevance_injects_entity_followup_for_active_task() -> None:
    decision = evaluate_task_state_relevance(
        "都可以 普通玉米",
        _active_task(
            task_type="crop_cycle_setup",
            missing_information=["品种"],
        ),
    )

    assert decision.should_inject is True
    assert decision.decision == "inject"
    assert decision.score >= 0.75


def test_relevance_rejects_weather_bypass_query() -> None:
    decision = evaluate_task_state_relevance(
        "天气怎么样？",
        _active_task(missing_information=["种植面积"]),
    )

    assert decision.should_inject is False
    assert decision.decision == "do_not_inject"
    assert decision.score < 0.4


def test_relevance_rejects_bypass_query_with_polite_confirmation_word() -> None:
    for user_input in [
        "天气可以吗",
        "今天可以浇水吗",
        "可以帮我查天气吗",
        "可以聊聊账号设置吗",
    ]:
        decision = evaluate_task_state_relevance(
            user_input,
            _active_task(missing_information=["种植面积"]),
        )

        assert decision.should_inject is False
        assert decision.decision == "do_not_inject"


def test_relevance_injects_unit_name_followup_for_crop_cycle_setup() -> None:
    decision = evaluate_task_state_relevance(
        "叫东棚",
        _active_task(
            task_type="crop_cycle_setup",
            missing_information=["种植单元名称"],
        ),
    )

    assert decision.should_inject is True
    assert decision.decision == "inject"
    assert decision.score >= 0.75
