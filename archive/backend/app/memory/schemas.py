"""Memory 服务输入 schema。"""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class MemoryObservationEvent:
    """一次 Agent 交互完成后的观察事件。"""

    user_id: str
    farm_id: int
    session_id: str | None
    user_input: str
    assistant_reply: str
    skills_called: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class MemorySearchQuery:
    """统一记忆检索查询。"""

    query: str
    user_id: str | None = None
    farm_id: int | None = None
    session_id: str | None = None
    limit: int = 5
    metadata: dict[str, Any] = field(default_factory=dict)
