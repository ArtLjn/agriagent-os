"""Memory 领域模型。"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal


MemoryRole = Literal["user", "assistant", "system", "tool"]
MemoryHitSource = Literal[
    "short_term",
    "user_preference",
    "farm_profile",
    "key_fact",
    "cycle_summary",
    "ledger_summary",
]


def utc_now() -> datetime:
    """返回带时区的当前时间。"""
    return datetime.now(UTC)


@dataclass(frozen=True)
class MemoryMessage:
    """短时记忆中的单条消息。"""

    role: MemoryRole
    content: str
    created_at: datetime = field(default_factory=utc_now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PendingActionSnapshot:
    """等待用户确认的写操作快照。"""

    action_id: str
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class TemporaryTaskState:
    """会话内临时任务状态。"""

    task_id: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(frozen=True)
class UserPreferenceMemory:
    """长期记忆：用户偏好占位结构。"""

    key: str
    value: str
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FarmProfileMemory:
    """长期记忆：农场画像占位结构。"""

    farm_id: int
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KeyFactMemory:
    """长期记忆：关键事实占位结构。"""

    fact: str
    source: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CycleSummaryMemory:
    """长期记忆：种植周期摘要占位结构。"""

    cycle_id: int | None
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LedgerSummaryMemory:
    """长期记忆：账务摘要占位结构。"""

    period: str
    summary: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LongTermMemoryContext:
    """长期记忆上下文。"""

    user_preferences: list[UserPreferenceMemory] = field(default_factory=list)
    farm_profiles: list[FarmProfileMemory] = field(default_factory=list)
    key_facts: list[KeyFactMemory] = field(default_factory=list)
    cycle_summaries: list[CycleSummaryMemory] = field(default_factory=list)
    ledger_summaries: list[LedgerSummaryMemory] = field(default_factory=list)

    def is_empty(self) -> bool:
        """判断长期记忆是否为空。"""
        return not any(
            [
                self.user_preferences,
                self.farm_profiles,
                self.key_facts,
                self.cycle_summaries,
                self.ledger_summaries,
            ]
        )


@dataclass(frozen=True)
class MemoryContext:
    """供 Context Builder 注入的记忆上下文。"""

    user_id: str
    farm_id: int
    session_id: str | None = None
    recent_messages: list[MemoryMessage] = field(default_factory=list)
    session_summary: str | None = None
    pending_action: PendingActionSnapshot | None = None
    temporary_task_state: TemporaryTaskState | None = None
    long_term: LongTermMemoryContext = field(default_factory=LongTermMemoryContext)
    retrieved_hits: list["MemoryHit"] = field(default_factory=list)

    def is_empty(self) -> bool:
        """判断可注入上下文是否为空。"""
        return (
            not self.recent_messages
            and self.session_summary is None
            and self.pending_action is None
            and self.temporary_task_state is None
            and self.long_term.is_empty()
            and not self.retrieved_hits
        )


@dataclass(frozen=True)
class MemoryHit:
    """统一检索结果结构。"""

    hit_id: str
    source: MemoryHitSource
    content: str
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
