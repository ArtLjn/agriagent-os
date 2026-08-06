import logging
import uuid

from sqlalchemy.orm import Session

from app.domains.users.password import hash_password
from app.domains.farm.models import Farm
from app.domains.users.models import User

logger = logging.getLogger(__name__)


def seed_default_farm(db: Session) -> None:
    """确保至少有一个默认农场（兼容旧数据无 user_id）。"""
    existing = db.query(Farm).filter(Farm.name == "默认农场").first()
    if existing:
        return
    db.add(Farm(name="默认农场"))
    db.commit()


def seed_admin_user(db: Session, phone: str, password: str) -> None:
    """根据配置自动创建管理员账号，并关联 Farm（仅当不存在时）。"""
    if not phone or not password:
        return
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        if existing.role != "admin":
            existing.role = "admin"
            db.commit()
            logger.info("已将用户 %s 提升为管理员", phone)
        # 确保管理员有关联 Farm
        farm = db.query(Farm).filter(Farm.user_id == existing.id).first()
        if not farm:
            db.add(Farm(name="管理员农场", user_id=existing.id))
            db.commit()
            logger.info("已为管理员 %s 创建关联农场", phone)
        return
    admin_id = str(uuid.uuid4())
    db.add(
        User(
            id=admin_id,
            phone=phone,
            password_hash=hash_password(password),
            nickname="系统管理员",
            role="admin",
            status="active",
        )
    )
    db.add(Farm(name="管理员农场", user_id=admin_id))
    db.commit()
    logger.info("已根据配置创建管理员账号 %s 并关联农场", phone)
