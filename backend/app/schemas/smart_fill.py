from typing import Any

from pydantic import BaseModel, Field


class SmartFillScenarioResponse(BaseModel):
    """智能填写场景元数据。"""

    key: str
    title: str
    description: str
    legacy_endpoint: str | None = None
    enabled: bool = True
    request_example: str


class SmartFillScenarioListResponse(BaseModel):
    """智能填写场景列表响应。"""

    items: list[SmartFillScenarioResponse]


class SmartFillParseRequest(BaseModel):
    """统一智能填写解析请求。"""

    scene: str = Field(..., min_length=1, max_length=80)
    text: str = Field(..., min_length=1, max_length=500)
    context: dict[str, Any] = Field(default_factory=dict)


class SmartFillParseResponse(BaseModel):
    """统一智能填写解析响应。"""

    scene: str
    draft: dict[str, Any]
    missing_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    trace_id: str | None = None


__all__ = [
    "SmartFillParseRequest",
    "SmartFillParseResponse",
    "SmartFillScenarioListResponse",
    "SmartFillScenarioResponse",
]
