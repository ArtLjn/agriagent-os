"""Agent Context、Session Snapshot 和 Memory 的可序列化数据模型。

这些模型只描述跨边界传递的数据契约，不负责读取 Mongo、Redis 或本地文件。
这样 Context Builder、Memory Service 和 Runtime 可以在不耦合具体存储的情况下交换
带租户范围、版本和预算信息的结构化对象。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any, ClassVar, TypeVar


class _ValueEnum(str, Enum):
    """让枚举既能作为字符串使用，也能安全写入 JSON。"""

    def __str__(self) -> str:
        return self.value


class ContextSource(_ValueEnum):
    """Context 或 Memory 数据的事实来源。"""

    CONVERSATION_MESSAGES = "conversation_messages"
    CONVERSATION_STATE = "conversation_state"
    REDIS_SNAPSHOT = "redis_snapshot"
    MEMORY_RECORDS = "memory_records"
    CURRENT_TURN = "current_turn"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


class SourceStatus(_ValueEnum):
    """来源当前是否可用于构建 Context。"""

    MONGO = "mongo"
    REDIS_SNAPSHOT = "redis_snapshot"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    CONFLICT = "conflict"
    INVALID = "invalid"


class ContextBlockStatus(_ValueEnum):
    """Context Block 在预算决策中的状态。"""

    CANDIDATE = "candidate"
    INCLUDED = "included"
    COMPRESSED = "compressed"
    DROPPED = "dropped"
    EXPIRED = "expired"
    UNAVAILABLE = "unavailable"


class BudgetDecision(_ValueEnum):
    """Context 预算器的最终决策。"""

    WITHIN_BUDGET = "within_budget"
    COMPRESSED = "compressed"
    DROPPED = "dropped"
    EXCEEDED = "exceeded"


class EstimationMode(_ValueEnum):
    """Token 使用量的计算模式。"""

    APPROXIMATE = "approximate"
    ACTUAL = "actual"


class ObservationStatus(_ValueEnum):
    """Memory observation 的生命周期状态。"""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class MemoryHitStatus(_ValueEnum):
    """长期 Memory 命中的新鲜度状态。"""

    ACTIVE = "active"
    STALE = "stale"
    EXPIRED = "expired"


_ModelT = TypeVar("_ModelT", bound="SerializableModel")


def _serialize(value: Any) -> Any:
    """递归转换 dataclass、枚举和容器，保持输出可直接 JSON 序列化。"""
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {
            item.name: _serialize(getattr(value, item.name)) for item in fields(value)
        }
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    return value


class SerializableModel:
    """提供统一的 dict/JSON 序列化入口，避免引入额外运行时依赖。"""

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {}

    def to_dict(self) -> dict[str, Any]:
        """返回只包含基础 JSON 类型的字典。"""
        return _serialize(self)

    def to_json(self) -> str:
        """返回稳定、中文可读的 JSON 表示。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)

    @classmethod
    def _parse_enum(cls, field_name: str, value: Any) -> Any:
        enum_type = cls._enum_fields.get(field_name)
        if value is None or enum_type is None or isinstance(value, enum_type):
            return value
        return enum_type(value)

    @classmethod
    def _base_values(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """只保留当前 dataclass 字段，并将枚举字符串恢复为枚举值。"""
        allowed = {item.name for item in fields(cls)}
        return {
            key: cls._parse_enum(key, value)
            for key, value in payload.items()
            if key in allowed
        }


@dataclass
class TokenBudget(SerializableModel):
    """一次 Context 构建的 token 预算和决策结果。"""

    model_context_tokens: int = 0
    response_reserve_tokens: int = 0
    safety_margin_tokens: int = 0
    message_tokens: int = 0
    tool_schema_tokens: int = 0
    tool_result_tokens: int = 0
    used_tokens: int = 0
    decision: BudgetDecision = BudgetDecision.WITHIN_BUDGET
    estimation_mode: EstimationMode = EstimationMode.APPROXIMATE

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "decision": BudgetDecision,
        "estimation_mode": EstimationMode,
    }

    @property
    def usable_tokens(self) -> int:
        """扣除模型输出预留和安全余量后可用于输入的 token 数。"""
        return max(
            self.model_context_tokens
            - self.response_reserve_tokens
            - self.safety_margin_tokens,
            0,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TokenBudget":
        return cls(**cls._base_values(payload))


@dataclass
class ConversationSnapshot(SerializableModel):
    """一个租户范围内 Conversation 的版本化 Short Memory 快照。"""

    conversation_id: str
    user_id: str
    farm_uid: str
    farm_id: int | None = None
    scope: str = "conversation"
    conversation_revision: int = 0
    summary_revision: int = 0
    reset_generation: int = 0
    source: ContextSource = ContextSource.EMPTY
    source_status: SourceStatus = SourceStatus.EMPTY
    recent_turns: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None
    pending_action: dict[str, Any] | None = None
    active_task_state: dict[str, Any] | None = None
    memory_revision: int = 0
    updated_at: str | None = None

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "source": ContextSource,
        "source_status": SourceStatus,
    }

    @property
    def revision(self) -> int:
        """兼容简写访问，同时以 conversation_revision 作为唯一存储字段。"""
        return self.conversation_revision

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ConversationSnapshot":
        values = dict(payload)
        if "conversation_revision" not in values and "revision" in values:
            values["conversation_revision"] = values["revision"]
        return cls(**cls._base_values(values))


@dataclass
class ContextBlock(SerializableModel):
    """可独立预算、压缩和追踪的 Context 片段。"""

    key: str
    content: Any
    source: ContextSource
    user_id: str
    farm_uid: str
    farm_id: int | None = None
    scope: str = "conversation"
    priority: int = 0
    required: bool = False
    compressible: bool = True
    min_tokens: int = 0
    estimated_tokens: int = 0
    status: ContextBlockStatus = ContextBlockStatus.CANDIDATE
    source_status: SourceStatus = SourceStatus.EMPTY
    version: int | str | None = None
    fresh_until: str | None = None
    drop_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "source": ContextSource,
        "status": ContextBlockStatus,
        "source_status": SourceStatus,
    }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ContextBlock":
        return cls(**cls._base_values(payload))


@dataclass
class ContextBundle(SerializableModel):
    """一次 LLM 调用的结构化 Context 输入投影。"""

    conversation_id: str
    turn_id: str
    user_id: str
    farm_uid: str
    farm_id: int | None = None
    scope: str = "conversation"
    conversation_revision: int = 0
    summary_revision: int = 0
    reset_generation: int = 0
    memory_revision: int = 0
    blocks: list[ContextBlock] = field(default_factory=list)
    budget: TokenBudget = field(default_factory=TokenBudget)
    source_status: SourceStatus = SourceStatus.EMPTY
    tool_schema_mode: str = "all"

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "source_status": SourceStatus,
    }

    @property
    def revision(self) -> int:
        """当前 Context 所依据的 Conversation revision。"""
        return self.conversation_revision

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ContextBundle":
        values = cls._base_values(payload)
        values["blocks"] = [
            ContextBlock.from_dict(item) for item in values.get("blocks", [])
        ]
        budget = values.get("budget", {})
        values["budget"] = (
            budget if isinstance(budget, TokenBudget) else TokenBudget.from_dict(budget)
        )
        return cls(**values)


@dataclass
class MemoryObservation(SerializableModel):
    """Turn 终态后提交给 Memory 层的受控观察事件。"""

    observation_id: str
    user_id: str
    farm_uid: str
    farm_id: int | None = None
    scope: str = "conversation"
    conversation_id: str = ""
    turn_id: str = ""
    conversation_revision: int = 0
    user_input_summary: str = ""
    assistant_response_summary: str = ""
    skills: list[str] = field(default_factory=list)
    status: ObservationStatus = ObservationStatus.PENDING
    source_status: SourceStatus = SourceStatus.EMPTY
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "status": ObservationStatus,
        "source_status": SourceStatus,
    }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryObservation":
        return cls(**cls._base_values(payload))


@dataclass
class MemoryHit(SerializableModel):
    """按 user/farm/domain scope 返回的长期 Memory 检索结果。"""

    memory_id: str
    content: str
    user_id: str
    farm_uid: str
    farm_id: int | None = None
    scope: str = "user"
    source: ContextSource = ContextSource.MEMORY_RECORDS
    source_status: SourceStatus = SourceStatus.EMPTY
    status: MemoryHitStatus = MemoryHitStatus.ACTIVE
    revision: int = 0
    score: float | None = None
    created_at: str | None = None
    expires_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "source": ContextSource,
        "source_status": SourceStatus,
        "status": MemoryHitStatus,
    }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MemoryHit":
        return cls(**cls._base_values(payload))
