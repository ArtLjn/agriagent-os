"""Agent history use case 测试。"""

from sqlalchemy import create_engine, event
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import sessionmaker
import pytest
from datetime import datetime

import app.application.session.history as history_use_case
from app.application.session.history import (
    list_conversation_items,
    list_message_items,
)
from app.shared.database import Base
from app.models.conversation import ConversationMessage
from app.models.farm import Farm
from app.services.conversation_service import get_or_create_conversation


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
    conv = get_or_create_conversation(
        db, farm_id=1, session_id="sess-summary", user_id="user-1"
    )
    conv.summary = "用户询问水稻种植情况，助手查询了农场状态。"
    conv.meta_json = {"title": "水稻种植", "preview": "当前有水稻", "category": "种植"}
    db.commit()

    items = list_conversation_items(db, farm=farm, limit=10)

    assert items[0].title == "水稻种植"
    assert items[0].preview == "当前有水稻"
    assert items[0].category == "种植"
    db.close()


def test_list_conversation_items_skips_empty_shell_conversations(monkeypatch):
    db = Session()
    farm = db.query(Farm).filter_by(id=1).one()
    get_or_create_conversation(db, farm_id=1, session_id="sess-empty", user_id="user-1")
    conv_with_message = get_or_create_conversation(
        db, farm_id=1, session_id="sess-message", user_id="user-1"
    )
    db.add(
        ConversationMessage(
            conversation_id=conv_with_message.id,
            role="user",
            content="你好",
        )
    )
    db.commit()

    def _messages(_db, session_id, farm_id):
        if session_id == "sess-message":
            return [ConversationMessage(role="user", content="你好")]
        return []

    monkeypatch.setattr(history_use_case, "get_conversation_messages", _messages)

    items = list_conversation_items(db, farm=farm, limit=10)

    assert [item.session_id for item in items] == ["sess-message"]
    db.close()


@pytest.mark.no_db
def test_list_conversation_items_uses_default_summary_when_messages_table_missing(
    monkeypatch,
):
    db = Session()
    farm = db.query(Farm).filter_by(id=1).one()
    get_or_create_conversation(db, farm_id=1, session_id="sess-drop", user_id="user-1")

    def _missing_messages(*_args, **_kwargs):
        raise ProgrammingError(
            "SELECT conversation_messages", {}, Exception("missing table")
        )

    monkeypatch.setattr(
        history_use_case,
        "get_conversation_messages",
        _missing_messages,
    )

    items = list_conversation_items(db, farm=farm, limit=10)

    assert items[0].title == "历史对话"
    assert items[0].preview == "点击查看这轮农事对话"
    db.close()


def test_list_message_items_prefers_meta_json_over_text_meta(monkeypatch):
    db = Session()
    farm = db.query(Farm).filter_by(id=1).one()
    conv = get_or_create_conversation(
        db, farm_id=1, session_id="sess-meta", user_id="user-1"
    )
    msg = ConversationMessage(
        id=1,
        conversation_id=conv.id,
        role="assistant",
        content="确认吗？",
        created_at=datetime(2026, 7, 6, 16, 0, 0),
    )
    msg.meta_json = {
        "skills": ["manage_workers"],
        "pending_action": {
            "action_id": "a1",
            "skill_name": "manage_workers",
            "params": {"姓名": "李一凡"},
            "context": {
                "original_input": "停用李一凡",
                "extracted_params": {},
                "notes": [],
            },
        },
    }

    monkeypatch.setattr(
        history_use_case,
        "get_conversation_messages",
        lambda *_args, **_kwargs: [msg],
    )

    items = list_message_items(db, farm=farm, session_id="sess-meta")

    assert items[0].skills == ["manage_workers"]
    assert items[0].pending_action is not None
    assert items[0].pending_action.action_id == "a1"
    db.close()
