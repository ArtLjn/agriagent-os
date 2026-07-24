"""认证服务 — 注册、登录、用户查询。"""

import logging
import uuid

from sqlalchemy.orm import Session

from app.domains.users.models import User
from app.domains.users.password import hash_password, verify_password
from app.domains.users.tokens import create_access_token
from app.domains.farm.service import create_default_farm

logger = logging.getLogger(__name__)


def register(
    db: Session, phone: str, password: str, nickname: str = "农友"
) -> tuple[User, str]:
    """注册新用户并通过 Farm 模块创建默认农场。"""
    user = create_user_with_default_farm(
        db,
        phone=phone,
        password=password,
        nickname=nickname,
    )
    token = create_access_token(user_id=user.id)
    logger.info("用户注册 | phone=%s user_id=%s", phone, user.id)
    return user, token


def create_user_with_default_farm(
    db: Session, *, phone: str, password: str, nickname: str = "农友"
) -> User:
    """创建普通用户和默认农场，不签发登录 token。"""
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        phone=phone,
        password_hash=hash_password(password),
        nickname=nickname,
    )
    db.add(user)
    create_default_farm(db, user_id=user_id, nickname=nickname)

    db.commit()
    db.refresh(user)

    logger.info("创建用户 | phone=%s user_id=%s", phone, user_id)
    return user


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
