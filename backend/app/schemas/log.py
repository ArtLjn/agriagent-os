from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class FarmLogBase(BaseModel):
    """农事日志基础 Schema。"""

    cycle_id: int
    operation_type: str
    operation_date: date
    operation_time: datetime | None = None
    note: str | None = None
    photo_urls: str | None = None


class FarmLogCreate(FarmLogBase):
    """创建农事日志请求 Schema。"""

    pass


class FarmLogResponse(FarmLogBase):
    """农事日志响应 Schema。"""

    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
