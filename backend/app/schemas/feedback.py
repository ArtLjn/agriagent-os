"""反馈相关 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackRequest(BaseModel):
    """提交反馈请求。"""

    message_id: int = Field(..., description="被评价的消息 ID")
    rating: str = Field(..., pattern="^(good|bad)$")
    correction: str | None = Field(None, max_length=500)


class FeedbackResponse(BaseModel):
    """反馈提交响应。"""

    id: int
    rating: str
    created_at: datetime

    model_config = {"from_attributes": True}
