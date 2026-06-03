"""测试评测指标。"""

from app.evaluation.cases.schemas import ExpectedSkillCall, ExpectedWriteOperation
from app.evaluation.metrics.context_quality import compute_context_quality
from app.evaluation.metrics.skill_quality import compute_skill_quality
from app.evaluation.replay.models import ActualSkillCall, ReplayResult


def test_compute_context_quality_metrics() -> None:
    results = [
        ReplayResult(
            case_id="case-1",
            passed=True,
            required_context_facts=["active_crop", "weather"],
            hit_context_facts=["active_crop"],
            context_drop_reasons=["budget_exceeded"],
            context_budget_used=80,
            context_budget_limit=100,
            retrieval_results_count=4,
            retrieval_results_used=2,
        )
    ]

    metrics = compute_context_quality(results)

    assert metrics.hit_rate == 0.5
    assert metrics.drop_reasons == {"budget_exceeded": 1}
    assert metrics.budget_usage_rate == 0.8
    assert metrics.retrieval_usage_rate == 0.5


def test_compute_skill_quality_metrics() -> None:
    results = [
        ReplayResult(
            case_id="case-1",
            passed=False,
            expected_skill_calls=[
                ExpectedSkillCall(
                    name="create_cost_record",
                    arguments={"amount": 300},
                ),
                ExpectedSkillCall(name="search_weather"),
            ],
            actual_skill_calls=[
                ActualSkillCall(
                    name="create_cost_record",
                    arguments={"amount": 30},
                ),
                ActualSkillCall(name="extra_tool"),
            ],
            expected_writes=[
                ExpectedWriteOperation(
                    table="cost_records",
                    operation="insert",
                    requires_confirmation=True,
                )
            ],
            write_confirmations_hit=0,
        )
    ]

    metrics = compute_skill_quality(results)

    assert metrics.accuracy == 0.5
    assert metrics.miss_rate == 0.5
    assert metrics.false_positive_rate == 0.5
    assert metrics.argument_accuracy == 0.0
    assert metrics.write_confirmation_hit_rate == 0.0
