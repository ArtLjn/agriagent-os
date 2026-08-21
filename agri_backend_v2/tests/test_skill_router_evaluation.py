"""Skill Router 回放门槛测试。"""

from agent.domains.harness.router.evaluation import ReplayCase, evaluate_replay


def test_router_replay_passes_recall_false_call_and_cost_gates() -> None:
    result = evaluate_replay(
        [
            ReplayCase(
                case_id="weather-1",
                expected_skills=frozenset({"weather"}),
                candidate_skills=frozenset({"weather"}),
                expected_tools=frozenset({"get_weather"}),
                called_tools=frozenset({"get_weather"}),
                candidate_tokens=100,
                all_tools_tokens=200,
            )
        ]
    )

    assert result.passed is True
    assert result.skill_recall == 1.0
    assert result.token_cost_reduction == 0.5


def test_router_replay_rejects_empty_or_low_quality_set() -> None:
    result = evaluate_replay([])

    assert result.passed is False
    assert result.failed_gates == ("empty_replay_set",)
