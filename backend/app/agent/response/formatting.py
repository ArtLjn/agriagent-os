"""Agent 回复格式化入口。"""

import json

from app.agent.response.models import ResponseEvent


def format_text_response(text: str) -> str:
    """返回规范化后的文本回复。"""
    return text.strip()


def format_sse_event(event: ResponseEvent) -> str:
    """把 ResponseEvent 渲染成 SSE data 行。"""
    if event.type == "done":
        return "data: [DONE]\n\n"
    return f"data: {json.dumps(event.payload, ensure_ascii=False)}\n\n"


__all__ = ["format_sse_event", "format_text_response"]
