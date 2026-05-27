"""User 模型测试。"""

import uuid

from app.core.database import SessionLocal
from app.models.user import User


def test_create_user_with_required_fields():
    """创建用户，必填字段正确保存。"""
    db = SessionLocal()
    try:
        user = User(
            id=str(uuid.uuid4()),
            phone="13800138000",
            password_hash="hashed",
            nickname="测试用户",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        found = db.query(User).filter(User.phone == "13800138000").first()
        assert found is not None
        assert found.nickname == "测试用户"
        assert found.role == "user"
        assert found.status == "active"
    finally:
        db.close()


def test_user_id_is_uuid_string():
    """用户 ID 为 UUID v4 字符串。"""
    db = SessionLocal()
    try:
        uid = str(uuid.uuid4())
        user = User(id=uid, phone="13900139000", password_hash="h")
        db.add(user)
        db.commit()

        found = db.get(User, uid)
        assert found is not None
        assert len(found.id) == 36
    finally:
        db.close()
