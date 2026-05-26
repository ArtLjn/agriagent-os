import logging

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.database import engine
from app.models.farm import Farm

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
                    text(
                        f"ALTER TABLE cost_records ADD COLUMN {col_name} {col_type}"
                    )
                )
                logger.info("已补列 cost_records.%s", col_name)


def seed_default_farm(db: Session) -> None:
    """向数据库插入默认农场记录（如不存在）。"""
    existing = db.query(Farm).filter(Farm.id == 1).first()
    if existing:
        return
    db.add(Farm(id=1, name="默认农场", owner_name="默认农户"))
    db.commit()
