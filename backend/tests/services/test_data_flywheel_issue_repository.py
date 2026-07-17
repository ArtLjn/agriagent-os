"""DataFlywheel 问题仓与规则候选包测试。"""

from datetime import datetime

import pytest

from app.models.data_flywheel import AgentReviewIssueChain
from app.platforms.data_flywheel.issue_repository import (
    build_issue_repository_entry,
    build_rule_candidate_package,
)

pytestmark = pytest.mark.no_db


def _accepted_crop_route_chain() -> AgentReviewIssueChain:
    return AgentReviewIssueChain(
        id=1,
        farm_id=1,
        chain_id="chain-1",
        session_id="sess-crop-route",
        trigger_turn_id=7,
        context_turn_ids=[5, 6],
        result_turn_ids=[8],
        status="accepted",
        severity="P1",
        dominant_signal="manual",
        final_labels=["wrong_tool_selection", "needs_regression"],
        source_label_ids=[],
        root_cause="作物清单查询被泛化农场状态工具过度匹配。",
        expected_behavior="查询当前种植作物时应调用茬口列表 Skill。",
        fix_target="router",
        reviewer_comment="测试过程中发现“我的作物”被路由到农场状态。",
        reviewer_id="admin-1",
        reviewed_at=datetime(2026, 7, 6, 14, 30, 0),
    )


def test_build_issue_repository_entry_projects_saved_chain() -> None:
    row = _accepted_crop_route_chain()

    entry = build_issue_repository_entry(
        row,
        user_input="我的作物",
        assistant_reply="这里是农场状态总览。",
        actual_skill="get_farm_status",
        expected_skill="get_crop_cycles",
        source="manual_test",
    )

    assert entry["issue_entry_id"] == "issue:chain-1"
    assert entry["chain_id"] == "chain-1"
    assert entry["source"] == "manual_test"
    assert entry["actual_skill"] == "get_farm_status"
    assert entry["expected_skill"] == "get_crop_cycles"
    assert entry["expected_behavior"] == "查询当前种植作物时应调用茬口列表 Skill。"
    assert entry["closure_state"] == "triaged"
    assert entry["related_turn_ids"] == [5, 6, 7, 8]


def test_build_rule_candidate_package_for_crop_inventory_route() -> None:
    row = _accepted_crop_route_chain()
    entry = build_issue_repository_entry(
        row,
        user_input="我的作物",
        assistant_reply="这里是农场状态总览。",
        actual_skill="get_farm_status",
        expected_skill="get_crop_cycles",
        source="manual_test",
    )

    package = build_rule_candidate_package(entry)

    assert package["candidate_id"] == (
        "crop_inventory_query_should_route_to_crop_cycles"
    )
    assert package["source_issue_ids"] == ["issue:chain-1"]
    assert package["failure_mode"] == (
        "broad_status_tool_overmatched_specific_crop_query"
    )
    assert package["target_layer"] == ["router_classifier", "skill_catalog"]
    assert package["expected_skill"] == "get_crop_cycles"
    assert package["wrong_skill"] == "get_farm_status"
    assert "我的作物" in package["positive_cases"]
    assert "今日天气对作物有什么影响" in package["negative_cases"]
    assert package["promotion_gate"]["positive_cases_must_pass"] is True
    assert package["status"] == "draft"
