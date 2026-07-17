"""流式聊天 use case 的事件和状态类型。"""

import json
from dataclasses import dataclass, field
from typing import Any, Literal

from app.application.session_flywheel import SessionFlywheelRecorder, StartedTurn
from app.models.conversation import Conversation
from app.schemas.agent import PendingActionResponse, PendingPlanResponse

ResponseEventType = Literal["content", "skills", "pending_action", "error", "done"]


@dataclass(frozen=True)
class ResponseEvent:
    """Agent application 向 API 层输出的事件。"""

    type: ResponseEventType
    payload: dict[str, Any] = field(default_factory=dict)


def format_text_response(text: str) -> str:
    """返回规范化后的文本回复。"""
    return text.strip()


def format_sse_event(event: ResponseEvent) -> str:
    """把 ResponseEvent 渲染成 SSE data 行。"""
    if event.type == "done":
        return "data: [DONE]\n\n"
    return f"data: {json.dumps(event.payload, ensure_ascii=False)}\n\n"


@dataclass
class StreamTurnContext:
    """流式会话 turn 的热路径上下文。"""

    recorder: SessionFlywheelRecorder
    started_at: float
    conversation: Conversation | None = None
    started_turn: StartedTurn | None = None


@dataclass
class StreamReplyState:
    """流式回复生成阶段积累的结果。"""

    full_reply: str = ""
    used_advisor: bool = False
    decision: object | None = None


@dataclass(frozen=True)
class StreamMetadata:
    """回复完成后的结构化尾部元数据。"""

    skill_names: list[str]
    pending_action: PendingActionResponse | None
    pending_plan: PendingPlanResponse | None
