"""Admin 用户管理 API — 列表、详情、状态管理。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.shared.database import get_db
from app.domains.users.dependencies import require_admin
from app.shared.config import settings
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.users.admin_schemas import (
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
    BatchUpdateUserQuotaRequest,
    BatchUpdateUserQuotaResponse,
    UpdateUserQuotaRequest,
    UpdateUserStatusRequest,
    UpdateUserStatusResponse,
    UserQuotaOverviewItem,
    UserQuotaOverviewResponse,
    UserQuotaStatus,
)
from app.domains.users.quota_service import (
    get_month_range,
    get_period_usage,
    get_user_quota_limits,
    get_week_range,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


def _quota_status_from_percent(monthly_percent: float, weekly_percent: float) -> str:
    if monthly_percent >= 1 or weekly_percent >= 1:
        return "exceeded"
    if monthly_percent >= 0.8 or weekly_percent >= 0.8:
        return "warning"
    return "normal"


def _build_quota_status(user_id: str, db: Session) -> UserQuotaStatus:
    month_start, month_end = get_month_range()
    week_start, week_end = get_week_range()
    limits = get_user_quota_limits(user_id, db)
    monthly_usage = get_period_usage(user_id, month_start, month_end, db)
    weekly_usage = get_period_usage(user_id, week_start, week_end, db)

    monthly_percent = (
        monthly_usage / limits.monthly_limit if limits.monthly_limit else 0
    )
    weekly_percent = weekly_usage / limits.weekly_limit if limits.weekly_limit else 0

    return UserQuotaStatus(
        monthly_limit=limits.monthly_limit,
        monthly_usage=monthly_usage,
        monthly_remaining=max(0, limits.monthly_limit - monthly_usage),
        monthly_start=month_start.isoformat(),
        monthly_end=month_end.isoformat(),
        weekly_limit=limits.weekly_limit,
        weekly_usage=weekly_usage,
        weekly_remaining=max(0, limits.weekly_limit - weekly_usage),
        weekly_start=week_start.isoformat(),
        weekly_end=week_end.isoformat(),
        status=_quota_status_from_percent(monthly_percent, weekly_percent),
    )


def _validate_quota_limits(
    token_monthly_limit: int | None,
    token_weekly_limit: int | None,
) -> None:
    """校验周额度不能超过月额度。"""
    monthly_limit = (
        token_monthly_limit
        if token_monthly_limit is not None
        else settings.token_quota.monthly_limit
    )
    weekly_limit = (
        token_weekly_limit
        if token_weekly_limit is not None
        else settings.token_quota.weekly_limit
    )
    if weekly_limit > monthly_limit:
        raise HTTPException(status_code=400, detail="周额度不能大于月额度")


@router.get("", response_model=AdminUserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, description="按状态筛选: active/disabled"),
    phone_keyword: str | None = Query(None, description="手机号模糊搜索"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminUserListResponse:
    """查询用户列表（分页、筛选）。"""
    query = db.query(User, Farm.name.label("farm_name")).outerjoin(
        Farm, Farm.user_id == User.id
    )

    if status:
        query = query.filter(User.status == status)
    if phone_keyword:
        query = query.filter(User.phone.contains(phone_keyword))

    total = query.count()
    rows = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    items = [
        AdminUserListItem(
            id=user.id,
            phone=user.phone,
            nickname=user.nickname,
            avatar_url=user.avatar_url,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
            farm_name=farm_name,
        )
        for user, farm_name in rows
    ]

    return AdminUserListResponse(items=items, total=total)


@router.get("/quota-overview", response_model=UserQuotaOverviewResponse)
def quota_overview(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, pattern="^(normal|warning|exceeded)$"),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UserQuotaOverviewResponse:
    """分页查询用户 Token 配额概览。"""
    users = db.query(User).order_by(User.created_at.desc()).all()
    items = []
    for user in users:
        quota = _build_quota_status(user.id, db)
        monthly_percent = (
            quota.monthly_usage / quota.monthly_limit if quota.monthly_limit else 0
        )
        weekly_percent = (
            quota.weekly_usage / quota.weekly_limit if quota.weekly_limit else 0
        )
        item = UserQuotaOverviewItem(
            user_id=user.id,
            nickname=user.nickname,
            phone=user.phone,
            monthly_limit=quota.monthly_limit,
            monthly_usage=quota.monthly_usage,
            monthly_percent=monthly_percent,
            weekly_limit=quota.weekly_limit,
            weekly_usage=quota.weekly_usage,
            weekly_percent=weekly_percent,
            status=quota.status,
        )
        if status is None or item.status == status:
            items.append(item)

    total = len(items)
    start = (page - 1) * size
    end = start + size
    return UserQuotaOverviewResponse(items=items[start:end], total=total)


@router.get("/{user_id}", response_model=AdminUserDetailResponse)
def get_user_detail(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> AdminUserDetailResponse:
    """获取用户详情（含农场信息）。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    farm = db.query(Farm).filter(Farm.user_id == user.id).first()

    return AdminUserDetailResponse(
        id=user.id,
        phone=user.phone,
        nickname=user.nickname,
        avatar_url=user.avatar_url,
        role=user.role,
        status=user.status,
        created_at=user.created_at,
        farm_id=farm.id if farm else None,
        farm_name=farm.name if farm else None,
        farm_location=farm.location if farm else None,
    )


@router.put("/quota/batch", response_model=BatchUpdateUserQuotaResponse)
def batch_update_user_quota(
    req: BatchUpdateUserQuotaRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> BatchUpdateUserQuotaResponse:
    """批量修改用户 Token 配额。"""
    _validate_quota_limits(req.token_monthly_limit, req.token_weekly_limit)
    users = db.query(User).filter(User.id.in_(req.user_ids)).all()
    if len(users) != len(set(req.user_ids)):
        found_ids = {user.id for user in users}
        missing_ids = [user_id for user_id in req.user_ids if user_id not in found_ids]
        raise HTTPException(
            status_code=404,
            detail=f"用户不存在: {', '.join(missing_ids)}",
        )

    for user in users:
        user.token_monthly_limit = req.token_monthly_limit
        user.token_weekly_limit = req.token_weekly_limit
    db.commit()

    return BatchUpdateUserQuotaResponse(
        updated_count=len(users),
        user_ids=[user.id for user in users],
    )


@router.get("/{user_id}/quota", response_model=UserQuotaStatus)
def get_user_quota(
    user_id: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UserQuotaStatus:
    """查询用户 Token 配额状态。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    return _build_quota_status(user.id, db)


@router.put("/{user_id}/quota", response_model=UserQuotaStatus)
def update_user_quota(
    user_id: str,
    req: UpdateUserQuotaRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UserQuotaStatus:
    """修改用户 Token 配额。"""
    _validate_quota_limits(req.token_monthly_limit, req.token_weekly_limit)
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.token_monthly_limit = req.token_monthly_limit
    user.token_weekly_limit = req.token_weekly_limit
    db.commit()
    db.refresh(user)

    return _build_quota_status(user.id, db)


@router.put("/{user_id}/status", response_model=UpdateUserStatusResponse)
def update_user_status(
    user_id: str,
    req: UpdateUserStatusRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> UpdateUserStatusResponse:
    """修改用户状态（禁用/启用）。"""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能修改管理员状态")

    user.status = req.status
    db.commit()

    return UpdateUserStatusResponse(id=user.id, status=user.status)
