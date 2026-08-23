"""认证服务 — 注册、登录、用户查询（从 archive 复用并适配 agri_backend_v2）。

变更点：
  - 移除 archive 的 `app.context.runtime` / `app.infra.repository_runtime` 依赖
  - 使用 agri_backend_v2 的 session_scope 替代直接传 db: Session
  - JWT 签发时注入 farm_uid（对外租户标识）和 farm_id（迁移期兼容）
  - 注册时自动创建默认农场和成本分类
"""

from __future__ import annotations

import logging
import uuid


from business.config import settings
from business.db import session_scope
from business.models import User
from business.services import farm_crud_service
from business.services.password import hash_password, verify_password
from business.services.tokens import create_access_token
from shared.roles import UserRole, normalize_user_role

logger = logging.getLogger(__name__)


def register(
    phone: str,
    password: str,
    nickname: str = "农友",
    role: str | UserRole = UserRole.USER,
) -> tuple[User, str]:
    """注册用户并创建默认农场；非普通角色只能由已授权管理端调用。

    Args:
        phone: 手机号（唯一）
        password: 明文密码（内部 hash 后存储）
        nickname: 昵称，默认 "农友"
        role: 角色；调用方必须在 API 边界完成管理员授权校验

    Returns:
        (user, access_token) 元组

    Raises:
        ValueError: 手机号已注册
    """
    normalized_role = normalize_user_role(role)
    with session_scope() as db:
        existing = db.query(User).filter(User.phone == phone).first()
        if existing is not None:
            raise ValueError(f"手机号 {phone} 已注册")

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            phone=phone,
            password_hash=hash_password(password),
            nickname=nickname,
            role=normalized_role.value,
            status="active",
        )
        db.add(user)
        # 农场通过外键引用用户；先落地用户行，再 flush 默认农场。
        db.flush()

        # 创建默认农场（farm_crud_service 内部 flush 拿到 farm.id）
        farm = farm_crud_service.create_default_farm(
            db, user_id=user_id, nickname=nickname
        )

        # 自动初始化默认成本分类（首次访问幂等）
        from business.services import cost_category_service

        cost_category_service.init_default_categories(db, farm_id=farm.id)

        db.flush()
        db.refresh(user)
        db.refresh(farm)

        token = create_access_token(
            user_id=user.id,
            phone=user.phone,
            role=normalized_role,
            farm_uid=farm.uid,
            farm_id=farm.id,
        )
        logger.info(
            "用户注册 | phone=%s user_id=%s farm_id=%s", phone, user.id, farm.id
        )
        return user, token


def login(phone: str, password: str) -> tuple[User, str] | None:
    """登录验证：手机号 + 密码匹配，返回 (user, token)。

    Args:
        phone: 手机号
        password: 明文密码

    Returns:
        (user, access_token) 元组；失败返回 None。
    """
    with session_scope() as db:
        user = db.query(User).filter(User.phone == phone).first()
        if user is None:
            return None
        if not verify_password(password, user.password_hash):
            return None
        if user.status != "active":
            return None

        # 解析关联农场 ID（用于 JWT 注入）
        farm = farm_crud_service.get_farm_by_user_id(db, user_id=user.id)
        farm_id = farm.id if farm else None

        if farm is None:
            return None
        token = create_access_token(
            user_id=user.id,
            phone=user.phone,
            role=user.role,
            farm_uid=farm.uid,
            farm_id=farm_id,
        )
        logger.info("用户登录 | phone=%s farm_id=%s", phone, farm_id)
        return user, token


def get_user_by_id(user_id: str) -> User | None:
    """通过 ID 查询用户。"""
    with session_scope() as db:
        return db.query(User).filter(User.id == user_id).first()


def ensure_admin_user() -> None:
    """启动时检查配置的管理员账号，不存在则自动创建。

    读取 config.auth.admin_phone / admin_password，为空则跳过。
    已存在同手机号用户则跳过（幂等）。
    """
    phone = settings.auth.admin_phone
    password = settings.auth.admin_password
    if not phone or not password:
        return

    with session_scope() as db:
        existing = db.query(User).filter(User.phone == phone).first()
        if existing is not None:
            return

        user_id = str(uuid.uuid4())
        user = User(
            id=user_id,
            phone=phone,
            password_hash=hash_password(password),
            nickname="管理员",
            role=UserRole.ADMIN.value,
            status="active",
        )
        db.add(user)
        # 管理员初始化同样需要先落地 users，避免 farms 外键插入失败。
        db.flush()

        farm = farm_crud_service.create_default_farm(
            db, user_id=user_id, nickname="管理员农场"
        )

        from business.services import cost_category_service

        cost_category_service.init_default_categories(db, farm_id=farm.id)
        db.flush()
        logger.info(
            "自动创建管理员 | phone=%s user_id=%s farm_id=%s",
            phone,
            user_id,
            farm.id,
        )


__all__ = [
    "register",
    "login",
    "get_user_by_id",
    "ensure_admin_user",
]
