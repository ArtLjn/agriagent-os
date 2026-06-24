"""PlanDraft 数据契约测试。"""

import pytest

from app.agent.planning.models import (
    PlanDraft,
    PlanIssue,
    PlanStep,
    PlanValidationResult,
)

pytestmark = pytest.mark.no_db


def test_plan_draft_serializes_supported_route_types() -> None:
    drafts = [
        PlanDraft(turn_id="", session_id="", farm_id=1, raw_user_input="你好", route_type="direct_reply"),
        PlanDraft(
            turn_id="",
            session_id="",
            farm_id=1,
            raw_user_input="我的工人有哪些",
            route_type="read_plan",
            steps=[PlanStep(step_id="read_workers", skill_name="get_workers")],
            selected_tools=["get_workers"],
        ),
        PlanDraft(
            turn_id="",
            session_id="",
            farm_id=1,
            raw_user_input="今天李海去6号棚压蔓工资100一天",
            route_type="write_pending_action",
            steps=[
                PlanStep(
                    step_id="create_work_order",
                    skill_name="create_operation_work_order",
                    risk="write_confirm",
                    params={"worker": "李海"},
                )
            ],
            selected_tools=["create_operation_work_order"],
        ),
        PlanDraft(
            turn_id="",
            session_id="",
            farm_id=1,
            raw_user_input="新来一个工人李丽工资100一天，今天去6号棚收水稻",
            route_type="write_pending_plan",
            steps=[
                PlanStep(step_id="create_worker", skill_name="manage_workers"),
                PlanStep(
                    step_id="create_work_order",
                    skill_name="create_operation_work_order",
                    depends_on=["create_worker"],
                ),
            ],
        ),
        PlanDraft(
            turn_id="",
            session_id="",
            farm_id=1,
            raw_user_input="李海这个月干了15天",
            route_type="clarification",
            missing_fields=["operation_type"],
            validation=PlanValidationResult(
                status="blocked",
                safe_route_type="clarification",
                missing_fields=["operation_type"],
                issues=[
                    PlanIssue(
                        code="missing_required_field",
                        message="缺少作业类型。",
                    )
                ],
            ),
        ),
    ]

    payloads = [draft.to_trace_payload() for draft in drafts]

    assert [payload["route_type"] for payload in payloads] == [
        "direct_reply",
        "read_plan",
        "write_pending_action",
        "write_pending_plan",
        "clarification",
    ]
    assert payloads[1]["selected_tools"] == ["get_workers"]
    assert payloads[2]["steps"][0]["skill_name"] == "create_operation_work_order"
    assert payloads[3]["steps"][1]["depends_on"] == ["create_worker"]
    assert payloads[4]["validation"]["issues"][0]["code"] == "missing_required_field"


def test_plan_draft_redacts_sensitive_trace_values() -> None:
    draft = PlanDraft(
        turn_id="",
        session_id="",
        farm_id=1,
        raw_user_input="保存 api_key=sk-secret",
        route_type="write_pending_action",
        evidence={"api_key": "sk-secret", "safe": "ok"},
        steps=[
            PlanStep(
                step_id="settings",
                skill_name="manage_user_settings",
                params={"password": "secret-value", "display_name": "李海"},
            )
        ],
    )

    payload = draft.to_trace_payload()

    assert payload["evidence"]["api_key"] == "[REDACTED]"
    assert payload["steps"][0]["params"]["password"] == "[REDACTED]"
    assert payload["steps"][0]["params"]["display_name"] == "李海"
