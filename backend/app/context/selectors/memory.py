"""Memory selector。"""

import json

from app.context.models import ContextBlock
from app.memory.models import (
    LongTermMemoryContext,
    MemoryContext,
    MemoryMessage,
    PendingActionSnapshot,
)


class MemorySelector:
    """选择短时或长期记忆摘要。"""

    def select(
        self,
        memory_summary: str | None = None,
        memory_hits: list[str] | None = None,
        memory_context: MemoryContext | None = None,
        **_kwargs,
    ) -> list[ContextBlock]:
        blocks = []
        if memory_context is not None:
            blocks.extend(self._select_short_term(memory_context))
            long_term_block = self._select_long_term(memory_context.long_term)
            if long_term_block is not None:
                blocks.append(long_term_block)

        legacy_block = self._select_legacy(memory_summary, memory_hits)
        if legacy_block is not None:
            blocks.append(legacy_block)
        return blocks

    def _select_long_term(
        self,
        long_term: LongTermMemoryContext,
    ) -> ContextBlock | None:
        if long_term.is_empty():
            return None

        lines: list[str] = []
        lines.extend(f"偏好：{item.value}" for item in long_term.user_preferences[:3])
        lines.extend(
            f"农场画像：{item.summary}" for item in long_term.farm_profiles[:2]
        )
        lines.extend(f"事实：{item.fact}" for item in long_term.key_facts[:3])
        lines.extend(
            f"账务摘要：{item.summary}" for item in long_term.ledger_summaries[:2]
        )
        if not lines:
            return None

        return ContextBlock(
            key="long_term_memory",
            source="memory.long_term",
            purpose="长期记忆",
            content="\n".join(lines[:5]),
            priority=55,
            compressible=True,
            min_tokens=48,
            metadata={"layer": "working", "cache_scope": "farm_user"},
        )

    def _select_legacy(
        self,
        memory_summary: str | None,
        memory_hits: list[str] | None,
    ) -> ContextBlock | None:
        parts: list[str] = []
        if memory_summary:
            parts.append(memory_summary)
        if memory_hits:
            parts.extend(memory_hits[:5])
        if not parts:
            return None
        return ContextBlock(
            key="memory",
            source="memory",
            purpose="记忆摘要",
            content="\n".join(parts),
            priority=45,
            compressible=True,
            min_tokens=32,
            metadata={"layer": "retrieval"},
        )

    def _select_short_term(self, memory_context: MemoryContext) -> list[ContextBlock]:
        blocks = []
        session_metadata = {"layer": "working", "cache_scope": "session"}

        if memory_context.recent_messages:
            blocks.append(
                ContextBlock(
                    key="short_term_recent",
                    source="memory.short_term",
                    purpose="最近对话",
                    content=self._format_recent_messages(
                        memory_context.recent_messages
                    ),
                    priority=70,
                    compressible=True,
                    min_tokens=48,
                    metadata=dict(session_metadata),
                )
            )

        if memory_context.session_summary:
            blocks.append(
                ContextBlock(
                    key="short_term_summary",
                    source="memory.short_term",
                    purpose="会话摘要",
                    content=memory_context.session_summary,
                    priority=50,
                    compressible=True,
                    metadata=dict(session_metadata),
                )
            )

        if memory_context.pending_action is not None:
            blocks.append(
                ContextBlock(
                    key="pending_action",
                    source="memory.short_term",
                    purpose="待确认动作",
                    content=self._format_pending_action(memory_context.pending_action),
                    priority=95,
                    required=True,
                    compressible=False,
                    metadata={
                        **session_metadata,
                        "required_reason": "pending_action",
                    },
                )
            )

        if memory_context.temporary_task_state is not None:
            blocks.append(
                ContextBlock(
                    key="temporary_task_state",
                    source="memory.short_term",
                    purpose="临时任务状态",
                    content=json.dumps(
                        {
                            "task_id": memory_context.temporary_task_state.task_id,
                            "status": memory_context.temporary_task_state.status,
                            "data": memory_context.temporary_task_state.data,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    priority=60,
                    compressible=True,
                    metadata=dict(session_metadata),
                )
            )
        return blocks

    @staticmethod
    def _format_recent_messages(messages: list[MemoryMessage]) -> str:
        return "\n".join(f"{message.role}：{message.content}" for message in messages)

    @staticmethod
    def _format_pending_action(pending_action: PendingActionSnapshot) -> str:
        return json.dumps(
            {
                "action_id": pending_action.action_id,
                "name": pending_action.name,
                "payload": pending_action.payload,
            },
            ensure_ascii=False,
            sort_keys=True,
        )


__all__ = ["MemorySelector"]
