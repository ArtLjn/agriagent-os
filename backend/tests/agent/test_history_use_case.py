"""Agent history use case 测试。"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.agent.application.history_use_case import list_conversation_items, list_message_items
from app.core.database import Base
from app.models.farm import Farm
from app.services.conversation_service import get_or_create_conversation, save_message


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_history_use_case.db",
    connect_args={"check_same_thread": False},
)
event.listen(_engine, "connect", _set_sqlite_pragma)
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def setup_function():
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    db = Session()
    db.add(Farm(id=1, name="默认农场", user_id="user-1"))
    db.commit()
    db.close()


def test_list_conversation_items_uses_summary_without_full_scan():
    db = Session()
    farm = db.query(Farm).filter_by(id=1).one()
    conv = get_or_create_conversation(db, farm_id=1, session_id="sess-summary", user_id="user-1")
    conv.summary = "用户询问水稻种植情况，助手查询了农场状态。"
    conv.meta_json = {"title": "水稻种植", "preview": "当前有水稻", "category": "种植"}
    db.commit()

    items = list_conversation_items(db, farm=farm, limit=10)

    assert items[0].title == "水稻种植"
    assert items[0].preview == "当前有水稻"
    assert items[0].category == "种植"
    db.close()


def test_list_message_items_prefers_meta_json_over_text_meta():
    db = Session()
    farm = db.query(Farm).filter_by(id=1).one()
    conv = get_or_create_conversation(db, farm_id=1, session_id="sess-meta", user_id="user-1")
    msg = save_message(db, conv.id, "assistant", "确认吗？")
    msg.meta_json = {
        "skills": ["manage_workers"],
        "pending_action": {
            "action_id": "a1",
            "skill_name": "manage_workers",
            "params": {"姓名": "李一凡"},
            "context": {"original_input": "停用李一凡", "extracted_params": {}, "notes": []},
        },
    }
    db.commit()

    items = list_message_items(db, farm=farm, session_id="sess-meta")

    assert items[0].skills == ["manage_workers"]
    assert items[0].pending_action is not None
    assert items[0].pending_action.action_id == "a1"
    db.close()
