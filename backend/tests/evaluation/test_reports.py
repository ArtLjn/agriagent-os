"""测试结构化评测报告。"""

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
                actual_skill_calls=[ActualSkillCall(name="create_cost_record")],
                latency_ms=120,
                token_cost=0.02,
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
    assert "created_at" in data
