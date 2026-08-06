"""Agent debug export API 测试。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.domains.conversation.routes import router
from app.shared.database import get_db
from app.shared.database import Base
from app.infra.limiter import limiter
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.users.tokens import create_access_token
from app.domains.conversation.service import get_or_create_conversation, save_message


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
    db.add(
        User(
            id="admin-user-001",
            phone="00000000999",
            password_hash="h",
            nickname="管理员",
            role="admin",
            status="active",
        )
    )
    db.add(Farm(id=2, name="管理员农场", user_id="admin-user-001"))
    db.add(
        User(
            id="sim-user-001",
            phone="00000000003",
            password_hash="h",
            nickname="模拟用户",
            status="active",
        )
    )
    db.add(Farm(id=3, name="模拟农场", user_id="sim-user-001"))
    sim_conv = get_or_create_conversation(
        db, farm_id=3, session_id="sess-sim-debug", user_id="sim-user-001"
    )
    save_message(db, sim_conv.id, "user", "模拟用户作物")
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

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_get_session_debug_export_v2():
    client = _client()

    response = client.get(
        "/agent/conversations/sess-debug/debug-export",
        headers=_headers_for("test-user-001"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "farm-manager.chat-session-debug.v2"
    assert "messages" in body
    assert "turns" in body
    assert "events" in body


def test_admin_simulated_user_debug_export_reads_target_farm():
    client = _client()

    response = client.get(
        "/agent/conversations/sess-sim-debug/debug-export"
        "?simulate_user_id=sim-user-001",
        headers=_headers_for("admin-user-001"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "farm-manager.chat-session-debug.v2"
    assert body["messages"][0]["content"] == "模拟用户作物"


def _headers_for(user_id: str) -> dict[str, str]:
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}
