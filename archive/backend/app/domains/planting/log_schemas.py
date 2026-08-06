from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class FarmLogBase(BaseModel):
    """农事日志基础 Schema。"""

    cycle_id: int
    work_order_id: int | None = None
    operation_type: str
    operation_date: date
    operation_time: datetime | None = None
    note: str | None = None
    photo_urls: str | None = None
    worker_ids: list[int] = Field(default_factory=list)
    worker_names: list[str] = Field(default_factory=list)


class FarmLogCreate(FarmLogBase):
    """创建农事日志请求 Schema。"""

    pass


class FarmLogResponse(FarmLogBase):
    """农事日志响应 Schema。"""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
