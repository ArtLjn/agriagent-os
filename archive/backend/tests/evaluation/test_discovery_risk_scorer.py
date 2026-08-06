"""DataFlywheel discovery risk scorer 测试。"""

from types import SimpleNamespace

from app.platforms.evaluation.discovery.risk_scorer import apply_risk_score, calculate_risk


def test_rule_signal_dominates_judge_signal() -> None:
    result = calculate_risk(rule_score=0.95, judge_bad_prob=0.7)

    assert result.risk_score == 0.95
    assert result.risk_dominant_signal == "rule"


def test_judge_signal_dominates_rule_signal() -> None:
    result = calculate_risk(rule_score=0, judge_bad_prob=0.82)

    assert result.risk_score == 0.82
    assert result.risk_dominant_signal == "judge"


def test_empty_signals_return_zero_and_no_dominant_signal() -> None:
    result = calculate_risk(rule_score=None, judge_bad_prob=None)

    assert result.risk_score == 0.0
    assert result.risk_dominant_signal is None


def test_boundary_values_are_supported() -> None:
    assert calculate_risk(rule_score=0, judge_bad_prob=0).risk_score == 0.0
    result = calculate_risk(rule_score=1, judge_bad_prob=0.99)

    assert result.risk_score == 1.0
    assert result.risk_dominant_signal == "rule"


def test_apply_risk_score_writes_object_fields() -> None:
    turn = SimpleNamespace(risk_score=None, risk_dominant_signal=None)

    result = apply_risk_score(turn, rule_score=0.2, judge_bad_prob=0.8)

    assert result.risk_score == 0.8
    assert turn.risk_score == 0.8
    assert turn.risk_dominant_signal == "judge"
