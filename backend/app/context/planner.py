"""Context 构建计划入口。"""

from app.context.policy import ContextBuildRequest, ContextPolicy, ContextPolicyResult


class ContextPlanner:
    """把请求解析为 selector、预算和依赖计划。"""

    def __init__(self, policy: ContextPolicy | None = None) -> None:
        self.policy = policy or ContextPolicy()

    def plan(self, request: ContextBuildRequest) -> ContextPolicyResult:
        """返回 Context Engine 可执行的构建计划。"""
        return self.policy.resolve(request)


__all__ = ["ContextPlanner"]
