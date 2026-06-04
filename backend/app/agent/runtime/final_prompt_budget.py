"""最终 prompt 预算检查。"""

from dataclasses import dataclass, field

from langchain_core.messages import BaseMessage, ToolMessage

from app.context.models import estimate_tokens


@dataclass(slots=True)
class FinalPromptBudgetResult:
    """最终 prompt 预算检查结果。"""

    system_tokens: int
    message_tokens: int
    tool_result_tokens: int
    total_tokens: int
    max_tokens: int
    over_budget: bool
    actions: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        """返回 trace 友好的摘要。"""
        return {
            "system_tokens": self.system_tokens,
            "message_tokens": self.message_tokens,
            "tool_result_tokens": self.tool_result_tokens,
            "total_tokens": self.total_tokens,
            "max_tokens": self.max_tokens,
            "over_budget": self.over_budget,
            "actions": list(self.actions),
        }


class FinalPromptBudget:
    """覆盖 system prompt、上下文、消息和工具结果的最终预算检查。"""

    def __init__(self, max_tokens: int = 6000, tool_result_limit: int = 800) -> None:
        self.max_tokens = max_tokens
        self.tool_result_limit = tool_result_limit

    def apply(
        self,
        system_text: str,
        messages: list[BaseMessage],
    ) -> tuple[list[BaseMessage], FinalPromptBudgetResult]:
        """必要时压缩消息，并返回预算结果。"""
        actions: list[str] = []
        compacted = list(messages)
        compacted, tool_action = self._compact_tool_results(compacted)
        if tool_action:
            actions.append(tool_action)

        result = self._measure(system_text, compacted, actions)
        if result.total_tokens <= self.max_tokens:
            return compacted, result

        compacted = self._drop_oldest_messages(compacted)
        actions.append("drop_oldest_messages")
        return compacted, self._measure(system_text, compacted, actions)

    def _measure(
        self, system_text: str, messages: list[BaseMessage], actions: list[str]
    ) -> FinalPromptBudgetResult:
        system_tokens = estimate_tokens(system_text)
        message_tokens = 0
        tool_result_tokens = 0
        for message in messages:
            tokens = estimate_tokens(str(message.content or ""))
            message_tokens += tokens
            if isinstance(message, ToolMessage):
                tool_result_tokens += tokens
        total_tokens = system_tokens + message_tokens
        return FinalPromptBudgetResult(
            system_tokens=system_tokens,
            message_tokens=message_tokens,
            tool_result_tokens=tool_result_tokens,
            total_tokens=total_tokens,
            max_tokens=self.max_tokens,
            over_budget=total_tokens > self.max_tokens,
            actions=list(actions),
        )

    def _compact_tool_results(
        self, messages: list[BaseMessage]
    ) -> tuple[list[BaseMessage], str | None]:
        changed = False
        result: list[BaseMessage] = []
        for message in messages:
            if not isinstance(message, ToolMessage):
                result.append(message)
                continue
            content = str(message.content or "")
            if estimate_tokens(content) <= self.tool_result_limit:
                result.append(message)
                continue
            changed = True
            result.append(
                ToolMessage(
                    content=content[: self.tool_result_limit * 2] + "\n[工具结果已压缩]",
                    tool_call_id=message.tool_call_id,
                )
            )
        return result, "compact_tool_results" if changed else None

    def _drop_oldest_messages(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        if len(messages) <= 4:
            return messages
        return messages[-4:]


__all__ = ["FinalPromptBudget", "FinalPromptBudgetResult"]
