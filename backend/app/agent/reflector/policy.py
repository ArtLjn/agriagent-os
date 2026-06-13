"""Agent Reflection 触发策略。"""

from langchain_core.messages import ToolMessage

from app.agent.reflector.models import ReflectionTrigger


class ReflectionPolicy:
    """判断某个节点是否需要运行 Reflection。"""

    def __init__(
        self,
        *,
        enabled: bool = True,
        pre_write_plan: bool = True,
        pre_execution: bool = True,
        post_tool_result: bool = True,
        fallback_guard: bool = True,
    ) -> None:
        self.enabled = enabled
        self.pre_write_plan = pre_write_plan
        self.pre_execution = pre_execution
        self.post_tool_result = post_tool_result
        self.fallback_guard = fallback_guard

    def should_run(
        self,
        *,
        trigger: ReflectionTrigger,
        intent: str = "agent",
        selected_tools: list[str] | None = None,
        tool_messages: list[ToolMessage] | None = None,
    ) -> bool:
        if not self.enabled:
            return False

        if trigger == ReflectionTrigger.PRE_WRITE_PLAN:
            return self.pre_write_plan
        if trigger == ReflectionTrigger.PRE_EXECUTION:
            return self.pre_execution
        if trigger in {
            ReflectionTrigger.POST_TOOL_RESULT,
            ReflectionTrigger.PRE_FINAL_RESPONSE,
        }:
            if not self.post_tool_result:
                return False
            return bool(selected_tools or tool_messages)
        if trigger == ReflectionTrigger.FALLBACK_GUARD:
            return self.fallback_guard

        return intent not in {"greeting", "chitchat"}
