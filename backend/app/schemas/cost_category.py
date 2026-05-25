"""成本分类 Schema，定义分类相关数据结构。"""

from pydantic import BaseModel, ConfigDict, field_validator


class CostCategoryBase(BaseModel):
    """成本分类基础 Schema。"""

    name: str
    type: str
    icon: str
    sort_order: int = 0

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证分类名称长度。"""
        if not (1 <= len(v) <= 50):
            raise ValueError("name 长度必须在 1-50 之间")
        return v

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证分类类型必须是 cost 或 income。"""
        if v not in ("cost", "income"):
            raise ValueError('type 必须是 "cost" 或 "income"')
        return v

    @field_validator("icon")
    @classmethod
    def validate_icon(cls, v: str) -> str:
        """验证图标名称长度。"""
        if not (1 <= len(v) <= 50):
            raise ValueError("icon 长度必须在 1-50 之间")
        return v

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, v: int) -> int:
        """验证排序值非负。"""
        if v < 0:
            raise ValueError("sort_order 必须大于等于 0")
        return v


class CostCategoryCreate(CostCategoryBase):
    """创建成本分类请求 Schema。"""

    pass


class CostCategoryResponse(CostCategoryBase):
    """成本分类响应 Schema。"""

    id: int
    farm_id: int
    is_default: bool

    model_config = ConfigDict(from_attributes=True)
