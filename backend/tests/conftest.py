"""公共测试 fixtures。"""

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.shared.database import get_db
from app.domains.users.dependencies import get_current_user
from app.domains.farm.dependencies import get_current_farm
from app.shared.database import Base
import app.shared.model_registry  # noqa: F401
from app.domains.users.tokens import create_access_token
from app.main import app
from app.domains.farm.models import Farm
from app.domains.users.models import User


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


_test_engine = create_engine(
    "sqlite:///tests/test_farm_manager.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def clean_db(request):
    if request.node.get_closest_marker("no_db"):
        yield
        return

    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)

    db = _TestSession()
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

    def _override_get_db():
        db = _TestSession()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_user():
        return User(
            id="test-user-001",
            phone="00000000000",
            password_hash="h",
            nickname="测试用户",
            role="user",
            status="active",
        )

    def override_get_current_farm(db=Depends(_override_get_db)):
        return db.query(Farm).filter(Farm.id == 1).first()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_current_farm] = override_get_current_farm

    yield

    app.dependency_overrides.clear()


@pytest.fixture()
def db_session():
    """提供隔离测试数据库会话。"""
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client():
    """API 测试客户端。"""
    return TestClient(app)


@pytest.fixture()
def auth_headers():
    """带有效 JWT 的请求头。"""
    token = create_access_token(user_id="test-user-001")
    return {"Authorization": f"Bearer {token}"}
