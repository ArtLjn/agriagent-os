"""DataFlywheel 风险评分辅助。"""

from dataclasses import dataclass
from typing import Literal

RiskDominantSignal = Literal["rule", "judge"] | None


@dataclass(frozen=True)
class RiskScoreResult:
    """风险分数与主导信号。"""

    risk_score: float
    risk_dominant_signal: RiskDominantSignal


def calculate_risk(
    *,
    rule_score: float | None,
    judge_bad_prob: float | None,
) -> RiskScoreResult:
    """按 max(rule_score, judge_bad_prob) 计算风险。"""

    normalized_rule = _normalize_score(rule_score)
    normalized_judge = _normalize_score(judge_bad_prob)

    if normalized_rule is None and normalized_judge is None:
        return RiskScoreResult(risk_score=0.0, risk_dominant_signal=None)

    rule_value = normalized_rule or 0.0
    judge_value = normalized_judge or 0.0
    if rule_value >= judge_value and normalized_rule is not None:
        return RiskScoreResult(
            risk_score=rule_value,
            risk_dominant_signal="rule",
        )
    return RiskScoreResult(
        risk_score=judge_value,
        risk_dominant_signal="judge",
    )


def apply_risk_score(
    target: object,
    *,
    rule_score: float | None,
    judge_bad_prob: float | None,
) -> RiskScoreResult:
    """把风险评分写入任意 turn-like 对象。"""

    result = calculate_risk(rule_score=rule_score, judge_bad_prob=judge_bad_prob)
    setattr(target, "risk_score", result.risk_score)
    setattr(target, "risk_dominant_signal", result.risk_dominant_signal)
    return result


def _normalize_score(value: float | None) -> float | None:
    if value is None:
        return None
    score = float(value)
    if score < 0 or score > 1:
        raise ValueError("risk signal must be between 0 and 1")
    return score
