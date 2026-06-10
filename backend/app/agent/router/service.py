"""Skill Router 服务入口。"""

from langchain_core.tools import BaseTool

from app.agent.router.catalog import SkillCatalog
from app.agent.router.classifier import RuleIntentClassifier
from app.agent.router.models import DisclosureBudget, RouterDecision
from app.agent.router.policy import RouterPolicy


class SkillRouter:
    """组合 catalog、classifier 与 policy 的路由服务。"""

    def __init__(
        self,
        classifier: RuleIntentClassifier | None = None,
        policy: RouterPolicy | None = None,
        budget: DisclosureBudget | None = None,
    ) -> None:
        self._classifier = classifier or RuleIntentClassifier()
        self._policy = policy or RouterPolicy(budget)

    def route(self, message: str, tools: list[BaseTool]) -> RouterDecision:
        """根据用户输入和可用工具返回路由决策。"""
        catalog = SkillCatalog.from_tools(tools)
        frames = self._classifier.classify(message)
        return self._policy.apply(
            message=message,
            frames=frames,
            candidates=catalog.enabled(),
        )
