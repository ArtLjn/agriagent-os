"""Admin 用户管理 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class AdminUserListItem(BaseModel):
    """用户列表项（含农场名）。"""

    id: str
    phone: str
    nickname: str
    avatar_url: str | None = None
    role: str
    status: str
    created_at: datetime
    farm_name: str | None = None

    model_config = {"from_attributes": True}


class AdminUserListResponse(PaginatedResponse[AdminUserListItem]):
    """用户列表分页响应。"""

    pass


class AdminUserDetailResponse(BaseModel):
    """用户详情（含农场信息）。"""

    id: str
    phone: str
    nickname: str
    avatar_url: str | None = None
    role: str
    status: str
    created_at: datetime
    farm_id: int | None = None
    farm_name: str | None = None
    farm_location: str | None = None

    model_config = {"from_attributes": True}


class UpdateUserStatusRequest(BaseModel):
    """修改用户状态请求。"""

    status: str = Field(..., pattern="^(active|disabled)$")


class UpdateUserStatusResponse(BaseModel):
    """修改用户状态响应。"""

    id: str
    status: str

    model_config = {"from_attributes": True}
