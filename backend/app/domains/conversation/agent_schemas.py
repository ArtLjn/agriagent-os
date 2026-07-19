"""Agent 相关请求与响应 Schema。"""

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class ChatRequest(BaseModel):
    """Agent 对话请求。"""

    cycle_id: int | None = None
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(None, max_length=64)
    simulate_user_id: str | None = Field(None, description="管理员模拟用户ID")


class PendingActionContext(BaseModel):
    """确认消息上下文。"""

    original_input: str = ""
    extracted_params: dict = {}
    notes: list[str] = []


class PendingActionResponse(BaseModel):
    """待确认操作信息，供前端展示确认 UI。"""

    action_id: str
    skill_name: str
    params: dict
    context: PendingActionContext | None = None


class PendingPlanResponse(BaseModel):
    """待确认计划信息，供前端展示确认 UI。"""

    plan_id: str
    status: str = "pending"
    raw_user_input: str = ""
    steps: list[dict] = []


class ChatResponse(BaseModel):
    """Agent 对话响应。"""

    reply: str
    pending_action: PendingActionResponse | None = None
    pending_plan: PendingPlanResponse | None = None
    model_config = ConfigDict(from_attributes=True)


DailyAdviceCategory = Literal[
    "weather",
    "operation",
    "crop_stage",
    "finance",
    "setup",
    "record",
]


class DailyAdviceOverviewMetric(BaseModel):
    """首页经营态势指标。"""

    key: str
    label: str
    value: str
    level: str = "normal"
    icon: str = "Activity"


class DailyAdviceOverview(BaseModel):
    """首页经营态势概览。"""

    score: int = Field(default=80, ge=0, le=100)
    subtitle: str = Field(default="今日经营状态平稳")
    metrics: list[DailyAdviceOverviewMetric] = Field(
        default_factory=lambda: [
            DailyAdviceOverviewMetric(
                key="weather",
                label="天气",
                value="天气平稳",
                level="normal",
                icon="CloudSun",
            ),
            DailyAdviceOverviewMetric(
                key="work_order",
                label="作业",
                value="0项",
                level="normal",
                icon="ClipboardList",
            ),
            DailyAdviceOverviewMetric(
                key="pending",
                label="待处理",
                value="0项",
                level="normal",
                icon="Bell",
            ),
        ]
    )


class DailyAdviceGeneration(BaseModel):
    """每日建议生成元数据。"""

    schema_version: str = "daily_advice_v2"
    mode: str = "legacy"
    retry_count: int = Field(default=0, ge=0)
    cache_hit: bool = False
    candidate_fingerprint: str | None = None


class DailyAdviceCompact(BaseModel):
    """首页列表使用的紧凑建议。"""

    title: str = Field(..., max_length=12)
    subtitle: str = Field(..., min_length=15, max_length=50)
    icon: str = Field(default="ClipboardList", max_length=40)
    icon_color: str = Field(default="gray", max_length=24)


class DailyAdviceHeroBadge(BaseModel):
    """详情页顶部标签。"""

    label: str
    value: str
    level: str = "normal"
    icon: str | None = None


class DailyAdviceEvidence(BaseModel):
    """建议判断依据。"""

    title: str
    description: str
    source_type: str
    source_id: int | None = None


class DailyAdviceStep(BaseModel):
    """建议执行步骤。"""

    title: str
    description: str = ""
    order: int = Field(..., ge=1)


class DailyAdviceRelatedEntry(BaseModel):
    """建议关联事项。"""

    title: str
    description: str = ""
    source_type: str
    source_id: int | None = None


class DailyAdviceAction(BaseModel):
    """建议操作入口。"""

    type: str
    label: str
    payload: dict = Field(default_factory=dict)


class DailyAdviceDetailView(BaseModel):
    """详情页使用的完整建议。"""

    title: str
    description: str = Field(..., min_length=20, max_length=120)
    hero_badges: list[DailyAdviceHeroBadge] = Field(default_factory=list)
    evidence: list[DailyAdviceEvidence] = Field(default_factory=list)
    steps: list[DailyAdviceStep] = Field(default_factory=list, min_length=2)
    related: list[DailyAdviceRelatedEntry] = Field(default_factory=list)
    actions: list[DailyAdviceAction] = Field(
        default_factory=lambda: [
            DailyAdviceAction(type="ask_agent", label="问问芽芽"),
        ],
        min_length=1,
    )

    @field_validator("actions")
    @classmethod
    def _must_include_ask_agent(
        cls,
        actions: list[DailyAdviceAction],
    ) -> list[DailyAdviceAction]:
        """详情动作至少保留问 Agent 入口。"""
        if not any(action.type == "ask_agent" for action in actions):
            raise ValueError("detail_view.actions 必须包含 ask_agent")
        return actions


class AdviceItem(BaseModel):
    """单条每日建议，兼容旧字段并提供 v2 展示结构。"""

    id: str = "legacy-advice"
    category: DailyAdviceCategory = "record"
    level: str = "normal"
    source_type: str = "legacy"
    source_id: int | None = None
    compact: DailyAdviceCompact | None = None
    detail_view: DailyAdviceDetailView | None = None

    title: str = Field(..., max_length=15)
    detail: str = Field(..., max_length=50)
    priority: int = Field(..., ge=1, le=3)
    icon: str = Field(default="📋", max_length=40)
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="before")
    @classmethod
    def _hydrate_v2_compat_fields(cls, data: object) -> object:
        """显式 compact 输入优先映射旧兼容字段。"""
        if not isinstance(data, dict):
            return data

        values = dict(data)
        compact = values.get("compact")
        compact_data = (
            compact.model_dump() if isinstance(compact, BaseModel) else compact
        )
        if isinstance(compact_data, dict):
            values["title"] = compact_data.get("title", "今日建议")
            values["detail"] = compact_data.get("subtitle", "")
            values["icon"] = compact_data.get("icon", "📋")
            if "priority" not in values:
                values["priority"] = compact_data.get("priority", 3)

        return values

    @model_validator(mode="after")
    def _fill_v2_display_fields(self) -> "AdviceItem":
        """旧字段输入通过原校验后，补齐 v2 展示字段。"""
        if self.compact is None:
            self.compact = DailyAdviceCompact(
                title=self.title[:12],
                subtitle=_pad_min_length(self.detail, 15)[:50],
                icon=self.icon,
                icon_color="gray",
            )

        if self.detail_view is None:
            self.detail_view = DailyAdviceDetailView(
                title=self.title,
                description=_pad_min_length(self.detail, 20),
                steps=[
                    DailyAdviceStep(
                        order=1,
                        title="查看建议内容",
                        description=self.detail,
                    ),
                    DailyAdviceStep(
                        order=2,
                        title="结合现场情况执行",
                        description="如需进一步判断，可继续咨询 Agent。",
                    ),
                ],
                actions=[DailyAdviceAction(type="ask_agent", label="问问芽芽")],
            )

        return self


class DailyAdviceResponse(BaseModel):
    """每日建议响应。"""

    cycle_id: int | None = None
    preview: str = Field(default="", max_length=20)
    overview: DailyAdviceOverview = Field(default_factory=DailyAdviceOverview)
    items: list[AdviceItem]
    generation: DailyAdviceGeneration = Field(default_factory=DailyAdviceGeneration)
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def advice(self) -> str:
        """向后兼容：拼接所有条目的 title+detail。"""
        if not self.items:
            return ""
        return "; ".join(f"{item.title}: {item.detail}" for item in self.items)


def _pad_min_length(value: str, min_length: int) -> str:
    """为旧字段兼容生成满足 v2 最小长度的详情描述。"""
    text = value.strip() or "暂无详细说明"
    while len(text) < min_length:
        text = f"{text}，请结合现场情况处理"
    return text[:120]


class ReportRequest(BaseModel):
    """报告生成请求。"""

    cycle_id: int | None = None
    report_type: str = "weekly"


class ReportResponse(BaseModel):
    """报告响应。"""

    cycle_id: int | None = None
    report_type: str
    content: str
    structured_data: dict | None = None
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
    report_type: str
    content: str
    structured_data: dict | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ReportListResponse(BaseModel):
    """报告历史列表响应。"""

    items: list[ReportHistoryItem]
    total: int
    model_config = ConfigDict(from_attributes=True)


class AppSkillItem(BaseModel):
    """App 技能展示项。"""

    key: str
    title: str
    description: str
    summary: str
    details: str
    examples: list[str] = []
    category: str
    icon: str
    icon_color: str
    recommended: bool = False
    enabled: bool = True


class AppSkillListResponse(BaseModel):
    """App 技能列表响应。"""

    items: list[AppSkillItem]
    total: int


class ConversationListItem(BaseModel):
    """会话列表项。"""

    id: int
    session_id: str
    status: str
    title: str = ""
    preview: str = ""
    category: str = "对话"
    created_at: datetime
    last_active_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ConversationMessageItem(BaseModel):
    """会话消息项。"""

    id: int
    role: str
    content: str
    skills: list[str] | None = None
    pending_action: PendingActionResponse | None = None
    pending_plan: PendingPlanResponse | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
