"""Agent Response 数据模型。"""

from dataclasses import dataclass, field
from typing import Any, Literal

ResponseEventType = Literal["content", "skills", "pending_action", "error", "done"]


@dataclass(frozen=True)
class ResponseEvent:
    """Agent application 向 API 层输出的事件。"""

    type: ResponseEventType
    payload: dict[str, Any] = field(default_factory=dict)
