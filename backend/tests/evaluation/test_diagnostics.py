"""Skill trace 诊断测试。"""

from types import SimpleNamespace

from app.evaluation.diagnostics import SkillDiagnosticService


def _record(
    *,
    id: int,
    node_type: str,
    node_name: str,
    output_data=None,
    input_data=None,
    status: str = "success",
    error_message=None,
):
    return SimpleNamespace(
        id=id,
        request_id="trace-1",
        round_index=0,
        node_type=node_type,
        node_name=node_name,
        input_data=input_data or {},
        output_data=output_data or {},
        status=status,
        error_message=error_message,
    )


def test_diagnostic_service_summarizes_trace_context_pending_and_errors() -> None:
    report = SkillDiagnosticService().build_report(
        "trace-1",
        [
            _record(
                id=1,
                node_type="context_build",
                node_name="context_bundle",
                output_data={
                    "context_dependency_diagnostics": [
                        {"block_key": "cycle", "status": "dropped"}
                    ]
                },
            ),
            _record(
                id=2,
                node_type="skill_call",
                node_name="update_crop_cycle",
                input_data={"start_date": "2026-09-01"},
            ),
            _record(
                id=3,
                node_type="pending_action",
                node_name="update_crop_cycle",
                output_data={
                    "status": "created",
                    "confirmation_context": {"changed_fields": ["start_date"]},
                },
            ),
            _record(
                id=4,
                node_type="skill_call",
                node_name="settle_labor_payment",
                status="error",
                error_message="validation failed",
            ),
            _record(
                id=5,
                node_type="final_response",
                node_name="assistant",
                output_data={"reply": "已生成待确认操作"},
            ),
        ],
    )

    assert report.tool_calls[0]["name"] == "update_crop_cycle"
    assert report.context_dependencies[0]["status"] == "dropped"
    assert report.pending_lifecycle[0]["structured_context"]["changed_fields"] == [
        "start_date"
    ]
    assert report.errors[0]["message"] == "validation failed"
    assert report.final_response == "已生成待确认操作"
    assert report.drilldown_links["timeline"] == "/admin/traces/trace-1/timeline"
    assert report.context_dependency_diagnostic[0]["diagnosis"] == (
        "selected_but_dropped_by_budget"
    )


def test_diagnostic_service_explains_tool_not_called() -> None:
    report = SkillDiagnosticService().build_report(
        "trace-1",
        [
            _record(
                id=1,
                node_type="tool_selector",
                node_name="selector",
                output_data={
                    "selected_tools": [],
                    "excluded_tools": ["update_crop_cycle"],
                },
            )
        ],
    )

    assert report.tool_not_called_reason == "tool_selection_excluded_skill"


def test_diagnostic_service_identifies_pending_action_lost_reason() -> None:
    report = SkillDiagnosticService().build_report(
        "trace-1",
        [
            _record(
                id=1,
                node_type="pending_action",
                node_name="create_cost_record",
                output_data={"status": "timed_out"},
            ),
            _record(
                id=2,
                node_type="final_response",
                node_name="assistant",
                output_data={"reply": "没有待确认操作"},
            ),
        ],
    )

    assert report.pending_action_diagnostic["lost_reason"] == "timed_out"
    assert "timed_out" in report.pending_action_diagnostic["statuses"]


def test_diagnostic_service_marks_unavailable_context_dependency() -> None:
    report = SkillDiagnosticService().build_report(
        "trace-1",
        [
            _record(
                id=1,
                node_type="context_build",
                node_name="context_bundle",
                output_data={
                    "context_dependency_diagnostics": [
                        {
                            "block_key": "cycle",
                            "dependencies": ["crop_cycle"],
                            "status": "unavailable",
                        }
                    ]
                },
            )
        ],
    )

    assert report.context_dependency_diagnostic == [
        {
            "block_key": "cycle",
            "dependencies": ["crop_cycle"],
            "status": "unavailable",
            "diagnosis": "unavailable_in_database_or_selector",
        }
    ]


def test_diagnostic_service_marks_not_selected_context_dependency() -> None:
    report = SkillDiagnosticService().build_report(
        "trace-1",
        [
            _record(
                id=1,
                node_type="context_build",
                node_name="context_bundle",
                output_data={
                    "policy": {
                        "context_dependency_map": {"cycle": ["crop_cycle"]},
                    },
                    "context_dependency_diagnostics": [],
                },
            )
        ],
    )

    assert report.context_dependency_diagnostic == [
        {
            "block_key": "cycle",
            "dependencies": ["crop_cycle"],
            "status": "not_selected",
            "diagnosis": "not_selected_by_context_policy",
        }
    ]


def test_diagnostic_service_records_pending_cache_invalidation() -> None:
    report = SkillDiagnosticService().build_report(
        "trace-1",
        [
            _record(
                id=1,
                node_type="pending_action",
                node_name="update_crop_cycle",
                output_data={
                    "status": "executed",
                    "metadata": {
                        "cache_groups_cleared": ["get_farm_status", "crop_cycle"],
                    },
                },
            )
        ],
    )

    assert report.pending_action_diagnostic["cache_invalidation"] == {
        "status": "recorded",
        "groups": ["crop_cycle", "get_farm_status"],
    }
