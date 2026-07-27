"""最终 prompt 预算检查。"""

from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.context.pipeline.compression import (
    CompressionEvent,
    compact_tool_result,
    tool_call_names_by_id,
)
from app.context.core.models import estimate_tokens


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
    message_count_before: int = 0
    message_count_after: int = 0
    tool_result_tokens_before: int = 0
    tool_result_tokens_after: int = 0
    compression_events: list[dict[str, Any]] = field(default_factory=list)

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
            "message_count_before": self.message_count_before,
            "message_count_after": self.message_count_after,
            "tool_result_tokens_before": self.tool_result_tokens_before,
            "tool_result_tokens_after": self.tool_result_tokens_after,
            "compression_events": list(self.compression_events),
        }


class FinalPromptBudget:
    """覆盖 system prompt、上下文、消息和工具结果的最终预算检查。"""

    def __init__(
        self,
        max_tokens: int = 6000,
        tool_result_limit: int = 800,
        recent_messages: int = 6,
        summary_item_limit: int = 12,
    ) -> None:
        self.max_tokens = max_tokens
        self.tool_result_limit = tool_result_limit
        self.recent_messages = recent_messages
        self.summary_item_limit = summary_item_limit

    def apply(
        self,
        system_text: str,
        messages: list[BaseMessage],
    ) -> tuple[list[BaseMessage], FinalPromptBudgetResult]:
        """必要时压缩消息，并返回预算结果。"""
        actions: list[str] = []
        message_count_before = len(messages)
        tool_result_tokens_before = self._tool_result_tokens(messages)
        compacted = list(messages)
        compacted, tool_action, compression_events = self._compact_tool_results(
            compacted
        )
        if tool_action:
            actions.append(tool_action)

        result = self._measure(
            system_text,
            compacted,
            actions,
            message_count_before=message_count_before,
            tool_result_tokens_before=tool_result_tokens_before,
            compression_events=compression_events,
        )
        if result.total_tokens <= self.max_tokens:
            return compacted, result

        compacted = self.summarize_old_messages(compacted)
        actions.append("summarize_old_messages")
        return compacted, self._measure(
            system_text,
            compacted,
            actions,
            message_count_before=message_count_before,
            tool_result_tokens_before=tool_result_tokens_before,
            compression_events=compression_events,
        )

    def _measure(
        self,
        system_text: str,
        messages: list[BaseMessage],
        actions: list[str],
        *,
        message_count_before: int,
        tool_result_tokens_before: int,
        compression_events: list[dict[str, Any]],
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
            message_count_before=message_count_before,
            message_count_after=len(messages),
            tool_result_tokens_before=tool_result_tokens_before,
            tool_result_tokens_after=tool_result_tokens,
            compression_events=list(compression_events),
        )

    def _compact_tool_results(
        self, messages: list[BaseMessage]
    ) -> tuple[list[BaseMessage], str | None, list[dict[str, Any]]]:
        changed = False
        compression_events: list[dict[str, Any]] = []
        result: list[BaseMessage] = []
        tool_names = tool_call_names_by_id(messages)
        for message in messages:
            if not isinstance(message, ToolMessage):
                result.append(message)
                continue
            content = str(message.content or "")
            original_tokens = estimate_tokens(content)
            if original_tokens <= self.tool_result_limit:
                result.append(message)
                continue
            changed = True
            compacted, event = self._compact_tool_message(
                message=message,
                content=content,
                original_tokens=original_tokens,
                tool_names=tool_names,
            )
            compression_events.append(event)
            result.append(compacted)
        return result, "compact_tool_results" if changed else None, compression_events

    def _compact_tool_message(
        self,
        *,
        message: ToolMessage,
        content: str,
        original_tokens: int,
        tool_names: dict[str, str],
    ) -> tuple[ToolMessage, dict[str, Any]]:
        tool_call_id = str(message.tool_call_id or "")
        status = getattr(message, "status", None)
        tool_name = getattr(message, "name", None) or tool_names.get(tool_call_id)
        compacted_content = compact_tool_result(
            content=content,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            status=str(status) if status else None,
            max_summary_chars=max(80, self.tool_result_limit * 2),
        )
        event = CompressionEvent(
            target="message",
            key=tool_call_id or "unknown_tool_call",
            action="compact_tool_results",
            reason="tool_result_over_limit",
            original_tokens=original_tokens,
            final_tokens=estimate_tokens(compacted_content),
            compressor="structured_tool_result",
            metadata={
                "tool_name": tool_name or "unknown",
                "status": str(status) if status else "unknown",
            },
        ).summary()
        return (
            ToolMessage(
                content=compacted_content,
                name=tool_name,
                tool_call_id=message.tool_call_id,
                status=status or "success",
            ),
            event,
        )

    @staticmethod
    def _tool_result_tokens(messages: list[BaseMessage]) -> int:
        return sum(
            estimate_tokens(str(message.content or ""))
            for message in messages
            if isinstance(message, ToolMessage)
        )

    def _drop_oldest_messages(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        if len(messages) <= 4:
            return messages
        return messages[-4:]

    def summarize_old_messages(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        if len(messages) <= self.recent_messages:
            return messages

        split_at = self._recent_window_start_index(messages)
        old_messages = messages[:split_at]
        recent = messages[split_at:]
        summary = self._build_message_summary(old_messages)
        return [AIMessage(content=summary), *recent]

    def _recent_window_start_index(self, messages: list[BaseMessage]) -> int:
        target = max(1, len(messages) - self.recent_messages)
        for index in range(target, -1, -1):
            if isinstance(messages[index], HumanMessage):
                return index
        return target

    def _build_message_summary(self, messages: list[BaseMessage]) -> str:
        lines = ["早期对话摘要："]
        omitted = max(0, len(messages) - self.summary_item_limit)
        for message in messages[-self.summary_item_limit :]:
            prefix = self._message_prefix(message)
            content = " ".join(str(message.content or "").split())
            if not content:
                continue
            lines.append(f"- {prefix}: {content[:80]}")
        if omitted:
            lines.insert(1, f"- 已省略更早的 {omitted} 条消息。")
        if len(lines) == 1:
            lines.append("- 无可用早期对话内容。")
        return "\n".join(lines)

    @staticmethod
    def _message_prefix(message: BaseMessage) -> str:
        if isinstance(message, HumanMessage):
            return "用户"
        if isinstance(message, ToolMessage):
            tool_name = message.name or "unknown"
            status = getattr(message, "status", None) or "unknown"
            return f"工具(name={tool_name}, status={status}, tool_call_id={message.tool_call_id})"
        return "助手"


__all__ = ["FinalPromptBudget", "FinalPromptBudgetResult"]
