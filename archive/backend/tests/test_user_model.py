"""User 模型测试。"""

import uuid

from app.domains.users.models import User


def test_create_user_with_required_fields(db_session):
    """创建用户，必填字段正确保存。"""
    user = User(
        id=str(uuid.uuid4()),
        phone="13800138000",
        password_hash="hashed",
        nickname="测试用户",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    found = db_session.query(User).filter(User.phone == "13800138000").first()
    assert found is not None
    assert found.nickname == "测试用户"
    assert found.role == "user"
    assert found.status == "active"


def test_user_id_is_uuid_string(db_session):
    """用户 ID 为 UUID v4 字符串。"""
    uid = str(uuid.uuid4())
    user = User(id=uid, phone="13900139000", password_hash="h")
    db_session.add(user)
    db_session.commit()

    found = db_session.get(User, uid)
    assert found is not None
    assert len(found.id) == 36
