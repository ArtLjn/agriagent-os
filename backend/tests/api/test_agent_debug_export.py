"""Agent debug export API 测试。"""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.api.agent import router
from app.shared.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.farm.dependencies import get_current_farm
from app.shared.database import Base
from app.infra.limiter import limiter
from app.models.farm import Farm
from app.models.user import User
from app.services.conversation_service import get_or_create_conversation, save_message


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_agent_debug_export_api.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(
        User(
            id="test-user-001",
            phone="00000000000",
            password_hash="h",
            nickname="测试用户",
            status="active",
        )
    )
    db.add(Farm(id=1, name="默认农场", user_id="test-user-001"))
    conv = get_or_create_conversation(
        db, farm_id=1, session_id="sess-debug", user_id="test-user-001"
    )
    save_message(db, conv.id, "user", "查一下作物")
    db.close()


def _client() -> TestClient:
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(router)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    def override_get_current_farm(db=Depends(override_get_db)) -> Farm:
        return db.query(Farm).filter(Farm.id == 1).one()

    def override_get_current_user() -> User:
        return User(
            id="test-user-001",
            phone="00000000000",
            password_hash="h",
            nickname="测试用户",
            role="user",
            status="active",
        )

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_farm] = override_get_current_farm
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app)


def test_get_session_debug_export_v2():
    client = _client()

    response = client.get("/agent/conversations/sess-debug/debug-export")

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "farm-manager.chat-session-debug.v2"
    assert "messages" in body
    assert "turns" in body
    assert "events" in body
