"""Agent 相关请求与响应 Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    cycle_id: int | None = None
    message: str


class ChatResponse(BaseModel):
    """Agent 对话响应。"""

    reply: str
    model_config = ConfigDict(from_attributes=True)


class DailyAdviceResponse(BaseModel):
    """每日建议响应。"""

    cycle_id: int | None = None
    advice: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportRequest(BaseModel):
    """报告生成请求。"""

    cycle_id: int | None = None
    report_type: str = "weekly"


class ReportResponse(BaseModel):
    """报告响应。"""

    cycle_id: int | None = None
    report_type: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AdviceHistoryItem(BaseModel):
    """建议历史记录项。"""

    id: int
    cycle_id: int | None = None
    advice_type: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportHistoryItem(BaseModel):
    """报告历史记录项。"""

    id: int
    cycle_id: int | None = None
    report_type: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
