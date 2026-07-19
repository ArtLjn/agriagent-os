"""Admin 用户管理 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.shared.schemas import PaginatedResponse


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


class UserQuotaStatus(BaseModel):
    """用户 Token 配额状态。"""

    monthly_limit: int
    monthly_usage: int
    monthly_remaining: int
    monthly_start: str
    monthly_end: str
    weekly_limit: int
    weekly_usage: int
    weekly_remaining: int
    weekly_start: str
    weekly_end: str
    status: str


class UpdateUserQuotaRequest(BaseModel):
    """修改用户 Token 配额请求。"""

    token_monthly_limit: int | None = Field(None, ge=0)
    token_weekly_limit: int | None = Field(None, ge=0)


class BatchUpdateUserQuotaRequest(UpdateUserQuotaRequest):
    """批量修改用户 Token 配额请求。"""

    user_ids: list[str] = Field(..., min_length=1, max_length=100)


class BatchUpdateUserQuotaResponse(BaseModel):
    """批量修改用户 Token 配额响应。"""

    updated_count: int
    user_ids: list[str]


class UserQuotaOverviewItem(BaseModel):
    """用户配额概览项。"""

    user_id: str
    nickname: str
    phone: str
    monthly_limit: int
    monthly_usage: int
    monthly_percent: float
    weekly_limit: int
    weekly_usage: int
    weekly_percent: float
    status: str


class UserQuotaOverviewResponse(PaginatedResponse[UserQuotaOverviewItem]):
    """用户配额概览分页响应。"""

    pass
