"""Skill Router 回放集评测与灰度门槛。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class ReplayCase:
    """一条脱敏回放样本，不包含用户凭证或完整对话。"""

    case_id: str
    expected_skills: frozenset[str]
    candidate_skills: frozenset[str]
    expected_tools: frozenset[str] = frozenset()
    called_tools: frozenset[str] = frozenset()
    candidate_tokens: int = 0
    all_tools_tokens: int = 0


@dataclass(frozen=True)
class RouterEvaluation:
    """回放集聚合指标和是否允许灰度。"""

    case_count: int
    skill_recall: float
    false_tool_rate: float
    token_cost_reduction: float
    passed: bool
    failed_gates: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_count": self.case_count,
            "skill_recall": self.skill_recall,
            "false_tool_rate": self.false_tool_rate,
            "token_cost_reduction": self.token_cost_reduction,
            "passed": self.passed,
            "failed_gates": list(self.failed_gates),
        }


def evaluate_replay(
    cases: Iterable[ReplayCase],
    *,
    min_skill_recall: float = 0.90,
    max_false_tool_rate: float = 0.05,
    min_token_cost_reduction: float = 0.10,
) -> RouterEvaluation:
    """按固定门槛评估 candidate Router，避免只看一次成功样本。"""
    items = list(cases)
    if not items:
        return RouterEvaluation(0, 0.0, 1.0, 0.0, False, ("empty_replay_set",))
    expected_skill_count = sum(len(item.expected_skills) for item in items)
    recalled_skill_count = sum(
        len(item.expected_skills & item.candidate_skills) for item in items
    )
    skill_recall = (
        recalled_skill_count / expected_skill_count if expected_skill_count else 1.0
    )
    false_calls = sum(len(item.called_tools - item.expected_tools) for item in items)
    expected_calls = sum(len(item.expected_tools) for item in items)
    false_tool_rate = false_calls / max(expected_calls, 1)
    candidate_tokens = sum(max(0, item.candidate_tokens) for item in items)
    all_tokens = sum(max(0, item.all_tools_tokens) for item in items)
    token_cost_reduction = (
        max(0, all_tokens - candidate_tokens) / all_tokens if all_tokens else 0.0
    )
    gates = []
    if skill_recall < min_skill_recall:
        gates.append("skill_recall_below_threshold")
    if false_tool_rate > max_false_tool_rate:
        gates.append("false_tool_rate_above_threshold")
    if token_cost_reduction < min_token_cost_reduction:
        gates.append("token_cost_reduction_below_threshold")
    return RouterEvaluation(
        case_count=len(items),
        skill_recall=round(skill_recall, 4),
        false_tool_rate=round(false_tool_rate, 4),
        token_cost_reduction=round(token_cost_reduction, 4),
        passed=not gates,
        failed_gates=tuple(gates),
    )


__all__ = ["ReplayCase", "RouterEvaluation", "evaluate_replay"]
