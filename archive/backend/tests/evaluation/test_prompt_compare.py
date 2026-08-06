"""测试 Prompt 版本对比。"""

from app.platforms.evaluation.replay.models import ActualSkillCall, ReplayResult
from app.platforms.evaluation.runners.prompt_compare import build_prompt_comparison


def test_build_prompt_comparison_outputs_required_deltas() -> None:
    base_results = [
        ReplayResult(
            case_id="case-1",
            passed=True,
            actual_skill_calls=[ActualSkillCall(name="create_cost_record")],
            latency_ms=100,
            token_cost=0.01,
        )
    ]
    candidate_results = [
        ReplayResult(
            case_id="case-1",
            passed=False,
            actual_skill_calls=[ActualSkillCall(name="search_weather")],
            latency_ms=130,
            token_cost=0.015,
        )
    ]

    comparison = build_prompt_comparison(
        "system_base:v1",
        "system_base:v2",
        base_results,
        candidate_results,
    )

    assert comparison.base_pass_rate == 1.0
    assert comparison.candidate_pass_rate == 0.0
    assert comparison.tool_call_differences["case-1"]["base"] == ["create_cost_record"]
    assert comparison.token_cost_delta == 0.004999999999999999
    assert comparison.avg_latency_delta_ms == 30
