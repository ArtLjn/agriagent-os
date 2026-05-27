"""认证服务 — 注册、登录、用户查询。"""

import uuid
import logging

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

logger = logging.getLogger(__name__)


def register(
    db: Session, phone: str, password: str, nickname: str = "农友"
) -> tuple[User, str]:
    """注册新用户。

    TODO: Task 5 后启用 Farm 创建 — 当前 Farm 模型缺少 user_id 字段。
    """
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        phone=phone,
        password_hash=hash_password(password),
        nickname=nickname,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user_id)
    logger.info("用户注册 | phone=%s user_id=%s", phone, user_id)
    return user, token


def login(db: Session, phone: str, password: str) -> tuple[User, str] | None:
    """登录验证，成功返回 (user, token)。"""
    user = db.query(User).filter(User.phone == phone).first()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    if user.status != "active":
        return None
    token = create_access_token(user_id=user.id)
    logger.info("用户登录 | phone=%s", phone)
    return user, token


def get_user_by_id(db: Session, user_id: str) -> User | None:
    """通过 ID 查询用户。"""
    return db.query(User).filter(User.id == user_id).first()
