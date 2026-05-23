from pydantic import BaseModel


class GrowthStageBase(BaseModel):
    """生长阶段基础 Schema。"""

    name: str
    duration_days: int
    order_index: int
    key_tasks: str | None = None


class GrowthStageCreate(GrowthStageBase):
    """创建生长阶段请求 Schema。"""

    pass


class GrowthStageResponse(GrowthStageBase):
    """生长阶段响应 Schema。"""

    id: int
    crop_template_id: int

    class Config:
        from_attributes = True


class CropTemplateBase(BaseModel):
    """作物模板基础 Schema。"""

    name: str
    variety: str | None = None


class CropTemplateCreate(CropTemplateBase):
    """创建作物模板请求 Schema，包含生长阶段列表。"""

    stages: list[GrowthStageCreate]


class CropTemplateResponse(CropTemplateBase):
    """作物模板响应 Schema，包含完整的生长阶段信息。"""

    id: int
    stages: list[GrowthStageResponse]

    class Config:
        from_attributes = True
