import logging
import uuid

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.core.security import hash_password
from app.models.farm import Farm
from app.models.user import User

logger = logging.getLogger(__name__)

# P1 新增列定义：(列名, SQL 类型)
_P1_NEW_COLUMNS = [
    ("record_subtype", "TEXT"),
    ("counterparty", "TEXT"),
    ("due_date", "TEXT"),
    ("settled_at", "TEXT"),
    ("parent_record_id", "INTEGER"),
]


def migrate_cost_records() -> None:
    """检测并补齐 cost_records 表中 P1 新增的列。"""
    insp = inspect(engine)
    if "cost_records" not in insp.get_table_names():
        return

    existing = {col["name"] for col in insp.get_columns("cost_records")}

    with engine.begin() as conn:
        for col_name, col_type in _P1_NEW_COLUMNS:
            if col_name not in existing:
                conn.execute(
                    text(f"ALTER TABLE cost_records ADD COLUMN {col_name} {col_type}")
                )
                logger.info("已补列 cost_records.%s", col_name)


def seed_default_farm(db: Session) -> None:
    """确保至少有一个默认农场（兼容旧数据无 user_id）。"""
    existing = db.query(Farm).filter(Farm.name == "默认农场").first()
    if existing:
        return
    db.add(Farm(name="默认农场"))
    db.commit()


def seed_admin_user(db: Session, phone: str, password: str) -> None:
    """根据配置自动创建管理员账号（仅当不存在时）。"""
    if not phone or not password:
        return
    existing = db.query(User).filter(User.phone == phone).first()
    if existing:
        if existing.role != "admin":
            existing.role = "admin"
            db.commit()
            logger.info("已将用户 %s 提升为管理员", phone)
        return
    db.add(
        User(
            id=str(uuid.uuid4()),
            phone=phone,
            password_hash=hash_password(password),
            nickname="系统管理员",
            role="admin",
            status="active",
        )
    )
    db.commit()
    logger.info("已根据配置创建管理员账号 %s", phone)
