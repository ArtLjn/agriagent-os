"""测试结构化评测报告。"""

import pytest

from app.platforms.evaluation.cases.schemas import ExpectedSkillCall
from app.platforms.evaluation.replay.models import ActualSkillCall, ReplayResult
from app.platforms.evaluation.reports.builder import EvaluationReportBuilder

pytestmark = pytest.mark.no_db


def test_report_builder_generates_ci_ready_report_dict() -> None:
    builder = EvaluationReportBuilder()
    report = builder.build(
        run_id="eval-001",
        results=[
            ReplayResult(
                case_id="case-1",
                passed=True,
                expected_skill_calls=[],
                actual_skill_calls=[ActualSkillCall(name="create_cost_record")],
                latency_ms=120,
                token_cost=0.02,
                drilldown_links={"timeline": "/admin/traces/abc/timeline"},
            )
        ],
        prompt_version="system_base:v1",
        config_summary={"mode": "unit"},
        code_version="abc123",
    )
    data = builder.to_dict(report)

    assert data["run_id"] == "eval-001"
    assert data["code_version"] == "abc123"
    assert data["prompt_version"] == "system_base:v1"
    assert data["metrics"]["pass_rate"] == 1.0
    assert data["cases"][0]["skill_calls"] == ["create_cost_record"]
    assert (
        data["cases"][0]["drilldown_links"]["timeline"] == "/admin/traces/abc/timeline"
    )
    assert "created_at" in data


def test_report_builder_groups_coverage_dimensions() -> None:
    builder = EvaluationReportBuilder()
    report = builder.build(
        run_id="eval-coverage",
        results=[
            ReplayResult(
                case_id="case-1",
                passed=True,
                expected_skill_calls=[ExpectedSkillCall(name="settle_labor_payment")],
                case_metadata={
                    "business_domain": "labor",
                    "permission_level": "write_confirm",
                    "confirmation_path": "confirm",
                    "context_dependencies": ["workers", "unpaid_labor"],
                },
            )
        ],
        prompt_version="system_base:v1",
    )

    assert report.coverage["by_skill"]["settle_labor_payment"] == 1
    assert report.coverage["by_business_domain"]["labor"] == 1
    assert report.coverage["by_permission_level"]["write_confirm"] == 1
    assert report.coverage["by_confirmation_path"]["confirm"] == 1
    assert report.coverage["by_context_dependency"]["workers"] == 1

def test_report_builder_counts_stage_level_failures() -> None:
    builder = EvaluationReportBuilder()
    report = builder.build(
        run_id="eval-stages",
        results=[
            ReplayResult(
                case_id="planning-miss",
                passed=False,
                errors=["bad_reply: 没有识别出压瓜作业写入意图"],
                case_metadata={"failure_stage": "planning"},
            ),
            ReplayResult(
                case_id="response-quality",
                passed=False,
                errors=["bad_reply: 无工具却声称已记录"],
                case_metadata={"failure_stage": "response_quality"},
            ),
            ReplayResult(
                case_id="validation",
                passed=False,
                errors=["missing operation_type"],
                case_metadata={"failure_stage": "validation"},
            ),
        ],
        prompt_version="system_base:v1",
    )
    data = builder.to_dict(report)

    assert data["coverage"]["by_failure_stage"] == {
        "planning": 1,
        "response_quality": 1,
        "validation": 1,
    }
    assert data["coverage"]["semantic_planning_failures"] == 1
    assert data["cases"][0]["failure_stage"] == "planning"


def test_report_builder_preserves_chain_metadata_for_failed_cases() -> None:
    builder = EvaluationReportBuilder()
    report = builder.build(
        run_id="eval-chain",
        results=[
            ReplayResult(
                case_id="regression-chain-1",
                passed=False,
                errors=["回复没有保留批量结算范围"],
                case_metadata={
                    "source": "data_flywheel_review_issue_chain",
                    "chain_id": "chain:1:sess-1:12",
                    "session_id": "sess-1",
                    "trigger_turn_id": 12,
                    "related_turn_ids": [11, 12, 13],
                },
            )
        ],
        prompt_version="system_base:v1",
    )
    data = builder.to_dict(report)

    assert data["cases"][0]["chain_id"] == "chain:1:sess-1:12"
    assert data["cases"][0]["metadata"]["chain_id"] == "chain:1:sess-1:12"
    assert data["cases"][0]["metadata"]["related_turn_ids"] == [11, 12, 13]
