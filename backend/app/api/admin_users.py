"""Admin 用户管理 API — 列表、详情、状态管理。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models.farm import Farm
from app.models.user import User
from app.schemas.admin_user import (
    AdminUserDetailResponse,
    AdminUserListItem,
    AdminUserListResponse,
    UpdateUserStatusRequest,
    UpdateUserStatusResponse,
)

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


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
