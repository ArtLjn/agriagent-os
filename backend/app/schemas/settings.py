"""用户设置相关 schema。"""

from pydantic import BaseModel, Field

__all__ = ["UserSettings", "UserSettingsUpdate"]


class UserSettings(BaseModel):
    """用户设置响应。"""

    display_name: str = "农友"


class UserSettingsUpdate(BaseModel):
    """用户设置更新请求。"""

    display_name: str = Field(default="农友", min_length=1, max_length=20)
