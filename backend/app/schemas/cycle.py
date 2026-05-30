from datetime import date

from pydantic import BaseModel, ConfigDict


class CycleStageBase(BaseModel):
    """茬口阶段基础 Schema。"""

    name: str
    start_date: date
    end_date: date
    order_index: int
    key_tasks: str | None = None
    is_current: bool = False


class CycleStageResponse(CycleStageBase):
    """茬口阶段响应 Schema。"""

    id: int
    cycle_id: int
    model_config = ConfigDict(from_attributes=True)


class CropCycleBase(BaseModel):
    """茬口基础 Schema。"""

    name: str
    crop_template_id: int
    start_date: date
    field_name: str | None = None


class CropCycleCreate(CropCycleBase):
    """创建茬口请求 Schema。"""

    pass


class CropCycleResponse(CropCycleBase):
    """茬口详情响应 Schema，包含阶段列表。"""

    id: int
    status: str
    stages: list[CycleStageResponse]
    model_config = ConfigDict(from_attributes=True)


class CropCycleListResponse(BaseModel):
    """茬口列表项响应 Schema。"""

    id: int
    name: str
    crop_template_name: str
    start_date: date
    status: str
    current_stage_name: str | None = None
    model_config = ConfigDict(from_attributes=True)


class CycleParseRequest(BaseModel):
    """AI 解析茬口请求 Schema。"""

    description: str


class CycleParseResponse(BaseModel):
    """AI 解析茬口响应 Schema。"""

    name: str
    crop_template_id: int | None = None
    start_date: str
    field_name: str | None = None
