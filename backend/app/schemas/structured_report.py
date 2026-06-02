"""结构化种植报告 Schema。

定义报告各组件的数据结构，供前端组件化渲染使用。
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportOverviewMetrics(BaseModel):
    """概览指标——报告顶部的关键数字。"""

    active_cycles: int = Field(..., ge=0, description="活跃茬口数")
    log_count: int = Field(..., ge=0, description="本周期农事记录数")
    total_cost: str = Field(..., description="本周期总支出")
    total_income: str = Field(..., description="本周期总收入")
    net_profit: str = Field(..., description="净利润")


class ReportCycleItem(BaseModel):
    """单个茬口报告项。"""

    cycle_id: int
    name: str
    field_name: str | None = None
    current_stage: str
    progress_percent: int = Field(..., ge=0, le=100)
    period_log_count: int = Field(..., ge=0, description="本周期内该茬口的农事数")
    total_stages: int = Field(..., ge=1)
    current_stage_index: int = Field(..., ge=1)
    days_elapsed: int = Field(..., ge=0, description="已种植天数")


class ReportCostItem(BaseModel):
    """成本/收入明细项。"""

    category: str
    amount: str
    record_type: str = Field(..., pattern="^(cost|income)$")
    record_date: date
    note: str | None = None


class ReportLogItem(BaseModel):
    """农事记录项。"""

    operation_type: str
    operation_date: date
    note: str | None = None
    cycle_name: str | None = None


class ReportAdviceItem(BaseModel):
    """AI 建议项。"""

    title: str = Field(..., max_length=20)
    detail: str = Field(..., max_length=100)
    priority: int = Field(..., ge=1, le=3)


class StructuredReportData(BaseModel):
    """完整的结构化报告数据。"""

    report_type: str = Field(..., pattern="^(weekly|monthly)$")
    period_start: date
    period_end: date
    overview: ReportOverviewMetrics
    cycles: list[ReportCycleItem]
    costs: list[ReportCostItem]
    logs: list[ReportLogItem]
    advice: list[ReportAdviceItem]
    summary: str = Field(..., max_length=200, description="AI 生成的简短总结")

    model_config = ConfigDict(from_attributes=True)


class StructuredReportResponse(BaseModel):
    """结构化报告 API 响应。"""

    cycle_id: int | None = None
    report_type: str
    content: str
    structured_data: StructuredReportData | None = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
