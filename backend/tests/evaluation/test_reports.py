"""测试结构化评测报告。"""

from app.evaluation.cases.schemas import ExpectedSkillCall
from app.evaluation.replay.models import ActualSkillCall, ReplayResult
from app.evaluation.reports.builder import EvaluationReportBuilder


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
    assert data["cases"][0]["drilldown_links"]["timeline"] == "/admin/traces/abc/timeline"
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
