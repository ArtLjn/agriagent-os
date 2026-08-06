"""Skill trace 诊断测试。"""

from types import SimpleNamespace

from app.platforms.evaluation.diagnostics import SkillDiagnosticService


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


def test_diagnostic_service_summarizes_reflection_checks() -> None:
    report = SkillDiagnosticService().build_report(
        "trace-1",
        [
            _record(
                id=1,
                node_type="reflection_check",
                node_name="pre_write_plan",
                input_data={"skill_name": "create_cost_record"},
                output_data={
                    "trigger": "pre_write_plan",
                    "decision": "ask_clarification",
                    "reason": "写操作参数不完整。",
                    "checks": ["write_plan_consistency"],
                    "issues": [
                        {
                            "code": "empty_write_params",
                            "severity": "blocker",
                            "message": "写操作参数为空。",
                        }
                    ],
                },
            ),
            _record(
                id=2,
                node_type="reflection_check",
                node_name="pre_final_response",
                input_data={"final_text": "已完成"},
                output_data={
                    "trigger": "pre_final_response",
                    "decision": "require_tool",
                    "reason": "最终回复缺少必要工具调用。",
                    "checks": ["required_tool_missing"],
                    "issues": [
                        {
                            "code": "required_tool_missing",
                            "severity": "blocker",
                            "message": "必须先调用工具。",
                        },
                        {
                            "code": "empty_write_params",
                            "severity": "warning",
                            "message": "重复 issue code 应去重。",
                        },
                    ],
                },
            ),
        ],
    )

    assert report.reflection_checks == [
        {
            "trigger": "pre_write_plan",
            "decision": "ask_clarification",
            "reason": "写操作参数不完整。",
            "checks": ["write_plan_consistency"],
            "issues": [
                {
                    "code": "empty_write_params",
                    "severity": "blocker",
                    "message": "写操作参数为空。",
                }
            ],
            "input": {"skill_name": "create_cost_record"},
        },
        {
            "trigger": "pre_final_response",
            "decision": "require_tool",
            "reason": "最终回复缺少必要工具调用。",
            "checks": ["required_tool_missing"],
            "issues": [
                {
                    "code": "required_tool_missing",
                    "severity": "blocker",
                    "message": "必须先调用工具。",
                },
                {
                    "code": "empty_write_params",
                    "severity": "warning",
                    "message": "重复 issue code 应去重。",
                },
            ],
            "input": {"final_text": "已完成"},
        },
    ]
    assert report.reflection_diagnostic == {
        "blocked": True,
        "decisions": ["ask_clarification", "require_tool"],
        "issue_codes": ["empty_write_params", "required_tool_missing"],
    }
    assert report.failure_stage == "response_quality"


def test_diagnostic_service_exposes_plan_draft_validation_summary() -> None:
    report = SkillDiagnosticService().build_report(
        "trace-plan-draft",
        [
            _record(
                id=1,
                node_type="plan_draft",
                node_name="plan_draft",
                output_data={
                    "route_type": "clarification",
                    "steps": [
                        {
                            "tool_name": "create_operation_work_order",
                            "params": {"worker_name": "李海"},
                        }
                    ],
                    "missing_fields": ["operation_type"],
                    "inferred_fields": [
                        {
                            "field": "unit_price",
                            "value": 100,
                            "source": "worker_default",
                        }
                    ],
                    "validation": {
                        "status": "blocked",
                        "missing_fields": ["operation_type"],
                        "inferred_fields": [
                            {
                                "field": "unit_price",
                                "source": "worker_default",
                            }
                        ],
                    },
                    "failure_stage": "validation",
                },
            )
        ],
    )

    assert report.plan_draft_summary == {
        "route_type": "clarification",
        "steps": ["create_operation_work_order"],
        "evidence": {},
    }
    assert report.validation_status == "blocked"
    assert report.missing_fields == ["operation_type"]
    assert report.inferred_fields == [
        {"field": "unit_price", "value": 100, "source": "worker_default"}
    ]
    assert report.failure_stage == "validation"


def test_diagnostic_service_distinguishes_semantic_selection_pending_execution_stages() -> None:
    semantic = SkillDiagnosticService().build_report(
        "trace-semantic",
        [
            _record(
                id=1,
                node_type="skill_router",
                node_name="skill_router",
                output_data={
                    "selected_tools": [],
                    "fallback": "clarify_farm_labor_work",
                    "frames": [
                        {
                            "intent": "clarify_farm_labor_work",
                            "missing_fields": ["operation_type"],
                        }
                    ],
                },
            )
        ],
    )
    selection = SkillDiagnosticService().build_report(
        "trace-selection",
        [
            _record(
                id=1,
                node_type="tool_selector",
                node_name="selector",
                output_data={"selected_tools": []},
            )
        ],
    )
    pending = SkillDiagnosticService().build_report(
        "trace-pending",
        [
            _record(
                id=1,
                node_type="skill_call",
                node_name="create_operation_work_order",
                output_data={"status": "reflection_blocked"},
            )
        ],
    )
    execution = SkillDiagnosticService().build_report(
        "trace-execution",
        [
            _record(
                id=1,
                node_type="skill_call",
                node_name="create_operation_work_order",
                status="error",
                error_message="数据库失败",
            )
        ],
    )

    assert semantic.failure_stage == "planning"
    assert selection.failure_stage == "selection"
    assert pending.failure_stage == "pending_creation"
    assert execution.failure_stage == "execution"
