"""公共测试 fixtures。"""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.api.deps import get_current_farm, get_current_user, get_db
from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token
from app.main import app
from app.models.farm import Farm
from app.models.user import User


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前重建表并播种默认用户和农场，同时覆盖依赖注入。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    user = User(
        id="test-user-001",
        phone="00000000000",
        password_hash="h",
        nickname="测试用户",
        status="active",
    )
    db.add(user)
    farm = Farm(id=1, name="默认农场", user_id="test-user-001")
    db.add(farm)
    db.commit()
    db.close()

    def override_get_current_user():
        return User(
            id="test-user-001",
            phone="00000000000",
            password_hash="h",
            nickname="测试用户",
            status="active",
        )

    def override_get_current_farm(db=Depends(get_db)):
        return db.query(Farm).filter(Farm.id == 1).first()

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_farm] = override_get_current_farm

    yield

    app.dependency_overrides.clear()


@pytest.fixture()
def client():
    """API 测试客户端。"""
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    """带有效 JWT 的请求头。"""
    token = create_access_token(user_id="test-user-001")
    return {"Authorization": f"Bearer {token}"}
