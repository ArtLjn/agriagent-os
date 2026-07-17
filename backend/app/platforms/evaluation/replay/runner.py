"""Agent 回放 runner 骨架。"""

from typing import Protocol

from app.platforms.evaluation.cases.schemas import AgentReplayCase
from app.platforms.evaluation.replay.models import ReplayResult, ReplayRunConfig


class AgentReplayExecutor(Protocol):
    """真实或测试 executor 需要实现的回放接口。"""

    async def run_case(
        self,
        case: AgentReplayCase,
        config: ReplayRunConfig,
    ) -> ReplayResult:
        """执行单个回放用例。"""


class ReplayRunner:
    """批量回放入口。"""

    def __init__(self, executor: AgentReplayExecutor) -> None:
        self._executor = executor

    async def run(
        self,
        cases: list[AgentReplayCase],
        config: ReplayRunConfig | None = None,
    ) -> list[ReplayResult]:
        """按顺序执行回放用例，便于稳定比较。"""
        run_config = config or ReplayRunConfig()
        return [await self._executor.run_case(case, run_config) for case in cases]
