"""Business REST API 共享请求模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class StrictRequest(BaseModel):
    """拒绝未声明字段，避免客户端拼写错误被静默忽略。"""

    model_config = ConfigDict(extra="forbid")


__all__ = ["StrictRequest"]
