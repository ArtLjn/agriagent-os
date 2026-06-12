"""用户设置相关 schema。"""

from typing import Optional

from pydantic import BaseModel, Field

from app.agent.assistant_roles import AssistantRole, DEFAULT_ASSISTANT_ROLE

__all__ = ["UserSettingsResponse", "UserSettingsUpdate"]


class UserSettingsResponse(BaseModel):
    """用户设置响应。"""

    display_name: str = "农友"
    default_city: Optional[str] = None
    default_lat: Optional[float] = None
    default_lon: Optional[float] = None
    assistant_role: AssistantRole = DEFAULT_ASSISTANT_ROLE


class UserSettingsUpdate(BaseModel):
    """用户设置更新请求。"""

    display_name: Optional[str] = Field(default=None, min_length=1, max_length=20)
    default_city: Optional[str] = Field(default=None, max_length=50)
    default_lat: Optional[float] = None
    default_lon: Optional[float] = None
    assistant_role: Optional[AssistantRole] = None
