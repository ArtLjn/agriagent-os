"""Skill Router 服务入口。"""

from copy import deepcopy

from langchain_core.tools import BaseTool

from app.agent.router.catalog import SkillCatalog
from app.agent.router.classifier import RuleIntentClassifier
from app.agent.router.models import DisclosureBudget, IntentFrame, RouterDecision
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

    def build_pending_plan_steps(self, decision: RouterDecision) -> list[dict]:
        """把多写入意图帧转换为 pending plan 存储步骤。"""
        write_frames = [
            frame
            for frame in decision.frames
            if frame.requires_confirmation and frame.params_hint
        ]
        if len(write_frames) < 2:
            return []

        return [
            {
                "step_id": frame.intent,
                "tool_name": self._tool_name_for_frame(frame),
                "params": self._params_for_frame(frame),
                "depends_on": list(frame.depends_on),
            }
            for frame in write_frames
        ]

    @staticmethod
    def _tool_name_for_frame(frame: IntentFrame) -> str:
        if frame.intent == "create_worker":
            return "manage_workers"
        if frame.intent == "create_work_order":
            return "create_operation_work_order"
        return frame.candidate_tools[0] if frame.candidate_tools else frame.intent

    @staticmethod
    def _params_for_frame(frame: IntentFrame) -> dict:
        params = deepcopy(frame.params_hint or {})
        if frame.intent == "create_worker":
            params.setdefault("action", "create")
        if frame.intent == "create_work_order":
            for key in ("workers", "unit_names"):
                if isinstance(params.get(key), list):
                    params[key] = ",".join(str(item) for item in params[key])
        return params
