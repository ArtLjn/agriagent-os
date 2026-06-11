"""Agent 数据飞轮模型测试。"""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.data_flywheel import AgentCaseDraft, AgentDataFlywheelLabel
from app.models.farm import Farm

pytestmark = pytest.mark.no_db


def _set_sqlite_pragma(dbapi_connection, _connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


_engine = create_engine(
    "sqlite:///tests/test_agent_data_flywheel_models.db",
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


def test_agent_data_flywheel_label_round_trip():
    db = Session()
    label = AgentDataFlywheelLabel(
        farm_id=1,
        sample_id="turn:1:sess-1:12",
        sample_type="session_turn",
        session_id="sess-1",
        turn_id=12,
        request_id="abcd1234",
        label="wrong_tool_selection",
        comment="选了写工具但实际只需要查询",
        annotator_id="admin-1",
    )
    db.add(label)
    db.commit()
    db.refresh(label)

    loaded = db.query(AgentDataFlywheelLabel).filter_by(id=label.id).one()

    assert loaded.id is not None
    assert loaded.sample_id == "turn:1:sess-1:12"
    assert loaded.label == "wrong_tool_selection"
    assert loaded.comment == "选了写工具但实际只需要查询"
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
    db.close()


def test_agent_case_draft_round_trip():
    db = Session()
    case_json = {
        "case_id": "regression-sess-1-12",
        "description": "王大妈工资缺失回归",
        "user_input": "王大妈工资 100 一天",
        "reply_assertions": [{"contains": "100"}],
        "metadata": {"source_sample_id": "turn:1:sess-1:12"},
    }
    draft = AgentCaseDraft(
        farm_id=1,
        draft_id="draft-abc123",
        source_sample_id="turn:1:sess-1:12",
        target_type="evaluation_replay",
        status="draft",
        case_json=case_json,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)

    loaded = db.query(AgentCaseDraft).filter_by(draft_id="draft-abc123").one()

    assert loaded.id is not None
    assert loaded.source_sample_id == "turn:1:sess-1:12"
    assert loaded.target_type == "evaluation_replay"
    assert loaded.status == "draft"
    assert loaded.case_json["case_id"] == "regression-sess-1-12"
    assert loaded.case_json["description"] == "王大妈工资缺失回归"
    assert loaded.case_json["user_input"] == "王大妈工资 100 一天"
    assert loaded.case_json["reply_assertions"] == [{"contains": "100"}]
    assert loaded.case_json["metadata"]["source_sample_id"] == "turn:1:sess-1:12"
    assert loaded.created_at is not None
    assert loaded.updated_at is not None
    db.close()
