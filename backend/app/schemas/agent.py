"""Agent 相关请求与响应 Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    cycle_id: int | None = None
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(None, max_length=64)


class PendingActionResponse(BaseModel):
    """待确认操作信息，供前端展示确认 UI。"""

    action_id: str
    skill_name: str
    params: dict


class ChatResponse(BaseModel):
    """Agent 对话响应。"""

    reply: str
    pending_action: PendingActionResponse | None = None
    model_config = ConfigDict(from_attributes=True)


class AdviceItem(BaseModel):
    """单条结构化建议。"""

    title: str = Field(..., max_length=15)
    detail: str = Field(..., max_length=50)
    priority: int = Field(..., ge=1, le=3)
    icon: str = Field(default="📋", max_length=4)


class DailyAdviceResponse(BaseModel):
    """每日建议响应。"""

    cycle_id: int | None = None
    items: list[AdviceItem]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def advice(self) -> str:
        """向后兼容：拼接所有条目的 title+detail。"""
        if not self.items:
            return ""
        return "; ".join(f"{item.title}: {item.detail}" for item in self.items)


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
    record_type: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportHistoryItem(BaseModel):
    """报告历史记录项。"""

    id: int
    cycle_id: int | None = None
    record_type: str
    content: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    """报告历史列表响应。"""

    items: list[ReportHistoryItem]
    total: int
    model_config = ConfigDict(from_attributes=True)


class ConversationListItem(BaseModel):
    """会话列表项。"""

    id: int
    session_id: str
    status: str
    created_at: datetime
    last_active_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ConversationMessageItem(BaseModel):
    """会话消息项。"""

    id: int
    role: str
    content: str
    skills: list[str] | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
