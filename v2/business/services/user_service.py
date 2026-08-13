"""用户服务 — 用户信息、用户设置（从 archive 复用并适配 v2）。

提供：
  - get_user_profile: 用户信息 + 农场信息
  - update_user_profile: 更新昵称/头像
  - get_user_settings / update_user_settings: 用户偏好设置
  - list_users / update_user_status: 管理员接口
"""
from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from sqlalchemy import or_

from business.db import session_scope
from business.models import User, UserSetting
from business.services import farm_crud_service

logger = logging.getLogger(__name__)


def get_user_profile(user_id: str) -> dict[str, Any] | None:
    """获取用户资料 + 绑定的农场信息。

    Args:
        user_id: 用户 ID

    Returns:
        {
            "id", "phone", "nickname", "avatar_url",
            "role", "status", "farm": {...}
        }
        不存在返回 None。
    """
    with session_scope() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None
        farm = farm_crud_service.get_farm_by_user_id(db, user_id=user.id)
        return {
            "id": user.id,
            "phone": user.phone,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "status": user.status,
            "farm": {
                "id": farm.id,
                "uid": farm.uid,
                "name": farm.name,
                "location": farm.location,
            }
            if farm
            else None,
        }


def update_user_profile(
    user_id: str,
    *,
    nickname: str | None = None,
    avatar_url: str | None = None,
) -> User | None:
    """更新用户资料（昵称、头像）。"""
    with session_scope() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None
        if nickname is not None:
            user.nickname = nickname
        if avatar_url is not None:
            user.avatar_url = avatar_url
        db.flush()
        farm = farm_crud_service.get_farm_by_user_id(db, user_id=user.id)
        return {
            "id": user.id,
            "phone": user.phone,
            "nickname": user.nickname,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "status": user.status,
            "farm": {
                "id": farm.id,
                "uid": farm.uid,
                "name": farm.name,
                "location": farm.location,
            }
            if farm
            else None,
        }


def get_user_settings(user_id: str) -> dict[str, Any] | None:
    """获取用户偏好设置。"""
    with session_scope() as db:
        setting = (
            db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
        )
        if setting is None:
            return None
        return {
            "user_id": setting.user_id,
            "default_city": setting.default_city,
            "default_lat": setting.default_lat,
            "default_lon": setting.default_lon,
            "assistant_role": setting.assistant_role,
        }


def update_user_settings(
    user_id: str,
    *,
    default_city: str | None = None,
    default_lat: float | None = None,
    default_lon: float | None = None,
    assistant_role: str | None = None,
) -> UserSetting:
    """更新用户偏好设置（不存在则创建）。

    如果更新了 default_city，同步更新关联农场的 location。
    """
    with session_scope() as db:
        setting = (
            db.query(UserSetting).filter(UserSetting.user_id == user_id).first()
        )
        if setting is None:
            setting = UserSetting(user_id=user_id, updated_at=datetime.now())
            db.add(setting)
        if default_city is not None:
            setting.default_city = default_city
        if default_lat is not None:
            setting.default_lat = default_lat
        if default_lon is not None:
            setting.default_lon = default_lon
        if assistant_role is not None:
            setting.assistant_role = assistant_role
        db.flush()
        return {
            "user_id": setting.user_id,
            "default_city": setting.default_city,
            "default_lat": setting.default_lat,
            "default_lon": setting.default_lon,
            "assistant_role": setting.assistant_role,
        }


# ─────────────────────────────────────────────────────────────
# 管理员接口
# ─────────────────────────────────────────────────────────────


def list_users(
    *,
    page: int = 1,
    size: int = 20,
    status: str | None = None,
    role: str | None = None,
    keyword: str | None = None,
) -> dict[str, Any]:
    """管理员：用户列表（分页）。

    Args:
        page: 页码（从 1 开始）
        size: 每页条数
        status: 按状态过滤（active/disabled）
        role: 按角色过滤（user/admin）
        keyword: 按手机号/昵称模糊搜索

    Returns:
        {"items": [...], "total": N}
    """
    with session_scope() as db:
        query = db.query(User)
        if status:
            query = query.filter(User.status == status)
        if role:
            query = query.filter(User.role == role)
        if keyword:
            kw = f"%{keyword.strip()}%"
            query = query.filter(
                or_(User.phone.like(kw), User.nickname.like(kw))
            )
        total = query.count()
        items = (
            query.order_by(User.created_at.desc())
            .offset((max(1, page) - 1) * size)
            .limit(size)
            .all()
        )
        return {
            "items": [_user_to_dict(u) for u in items],
            "total": total,
        }


def update_user_status(user_id: str, status: str) -> User | None:
    """管理员：启用/禁用用户。"""
    with session_scope() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None
        user.status = status
        db.flush()
        return user


def update_user_quota(
    user_id: str,
    *,
    token_monthly_limit: int | None = None,
    token_weekly_limit: int | None = None,
) -> User | None:
    """管理员：更新用户 Token 配额。"""
    with session_scope() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            return None
        if token_monthly_limit is not None:
            user.token_monthly_limit = token_monthly_limit
        if token_weekly_limit is not None:
            user.token_weekly_limit = token_weekly_limit
        db.flush()
        return user


def _user_to_dict(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "phone": user.phone,
        "nickname": user.nickname,
        "avatar_url": user.avatar_url,
        "role": user.role,
        "status": user.status,
        "token_monthly_limit": user.token_monthly_limit,
        "token_weekly_limit": user.token_weekly_limit,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


__all__ = [
    "get_user_profile",
    "update_user_profile",
    "get_user_settings",
    "update_user_settings",
    "list_users",
    "update_user_status",
    "update_user_quota",
]
