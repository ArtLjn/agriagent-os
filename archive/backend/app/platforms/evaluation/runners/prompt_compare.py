"""Prompt 版本对比评测。"""

from dataclasses import dataclass

from app.platforms.evaluation.cases.schemas import AgentReplayCase
from app.platforms.evaluation.replay.models import ReplayResult, ReplayRunConfig
from app.platforms.evaluation.replay.runner import AgentReplayExecutor, ReplayRunner


@dataclass
class PromptComparisonResult:
    """两个 Prompt 版本的差异摘要。"""

    base_version: str
    candidate_version: str
    base_pass_rate: float
    candidate_pass_rate: float
    tool_call_differences: dict[str, dict[str, list[str]]]
    token_cost_delta: float
    avg_latency_delta_ms: float


class PromptComparisonRunner:
    """对同一批用例比较两个 Prompt 版本。"""

    def __init__(self, executor: AgentReplayExecutor) -> None:
        self._runner = ReplayRunner(executor)

    async def compare(
        self,
        cases: list[AgentReplayCase],
        base_version: str,
        candidate_version: str,
    ) -> PromptComparisonResult:
        base_results = await self._runner.run(
            cases,
            ReplayRunConfig(prompt_version=base_version),
        )
        candidate_results = await self._runner.run(
            cases,
            ReplayRunConfig(prompt_version=candidate_version),
        )
        return build_prompt_comparison(
            base_version,
            candidate_version,
            base_results,
            candidate_results,
        )


def build_prompt_comparison(
    base_version: str,
    candidate_version: str,
    base_results: list[ReplayResult],
    candidate_results: list[ReplayResult],
) -> PromptComparisonResult:
    """根据两组结果生成 Prompt 差异。"""
    base_by_case = {result.case_id: result for result in base_results}
    candidate_by_case = {result.case_id: result for result in candidate_results}
    common_case_ids = sorted(base_by_case.keys() & candidate_by_case.keys())

    differences: dict[str, dict[str, list[str]]] = {}
    for case_id in common_case_ids:
        base_tools = [call.name for call in base_by_case[case_id].actual_skill_calls]
        candidate_tools = [
            call.name for call in candidate_by_case[case_id].actual_skill_calls
        ]
        if base_tools != candidate_tools:
            differences[case_id] = {
                "base": base_tools,
                "candidate": candidate_tools,
            }

    return PromptComparisonResult(
        base_version=base_version,
        candidate_version=candidate_version,
        base_pass_rate=_pass_rate(base_results),
        candidate_pass_rate=_pass_rate(candidate_results),
        tool_call_differences=differences,
        token_cost_delta=sum(r.token_cost for r in candidate_results)
        - sum(r.token_cost for r in base_results),
        avg_latency_delta_ms=_avg_latency(candidate_results)
        - _avg_latency(base_results),
    )


def _pass_rate(results: list[ReplayResult]) -> float:
    return (
        sum(1 for result in results if result.passed) / len(results) if results else 0.0
    )


def _avg_latency(results: list[ReplayResult]) -> float:
    return (
        sum(result.latency_ms for result in results) / len(results) if results else 0.0
    )
