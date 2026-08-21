"""Memory 层跨模块使用的数据契约。

Context 模块负责通用的 Context/Memory 记录模型；本模块只补充 Memory
边界需要的 Session View 和租户范围类型，避免存储实现反向污染 Runtime。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

from agent.domains.harness.context.models import (
    MemoryHit,
    MemoryHitStatus,
    MemoryObservation,
    ObservationStatus,
    SourceStatus,
)


class SessionView(TypedDict, total=False):
    """Memory Service 返回给 Context Builder 的短时记忆投影。

    使用 TypedDict 保留当前字典契约，避免迁移期间迫使 Runtime 一次性改成
    dataclass；字段仍由 ``short_term.empty_session_view`` 统一初始化。
    """

    conversation_id: str
    user_id: str
    farm_id: int
    farm_uid: str
    messages: list[dict[str, Any]]
    recent_turns: list[dict[str, Any]]
    summary: str | None
    summary_revision: int
    summary_status: str
    summary_source_from_message_id: str | None
    summary_source_to_message_id: str | None
    summary_source_conversation_revision: int | None
    summary_content_hash: str | None
    conversation_revision: int
    reset_generation: int
    pending_action: dict[str, Any] | None
    task_state: dict[str, Any] | None
    source_status: str
    source_divergence: dict[str, Any]
    long_term: dict[str, Any]


@dataclass(frozen=True)
class MemoryScope:
    """长期记忆检索或写入必须携带的可信租户范围。"""

    user_id: str
    farm_id: int
    scope: str = "farm"
    domain: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """转换成 Memory adapter 可消费的基础字典。"""
        result: dict[str, Any] = {
            "user_id": self.user_id,
            "farm_id": self.farm_id,
            "scope": self.scope,
        }
        if self.domain:
            result["domain"] = self.domain
        return result


MemorySearchResult = list[dict[str, Any]]


__all__ = [
    "MemoryHit",
    "MemoryHitStatus",
    "MemoryObservation",
    "MemoryScope",
    "MemorySearchResult",
    "ObservationStatus",
    "SessionView",
    "SourceStatus",
]
