from pydantic import BaseModel, ConfigDict, Field


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


class CropTemplateParseRequest(BaseModel):
    """AI 解析作物模板请求 Schema。"""

    description: str = Field(
        ..., min_length=1, max_length=500, description="自然语言作物描述"
    )


class CropTemplateParseResponse(BaseModel):
    """AI 解析作物模板响应 Schema。"""

    name: str = Field(..., description="作物名称")
    variety: str | None = Field(None, description="品种名称")
    stages: list[GrowthStageCreate] = Field(..., description="生长阶段列表")
