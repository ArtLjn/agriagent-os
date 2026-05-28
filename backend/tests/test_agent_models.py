import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, _set_sqlite_pragma
from app.models.agent_record import AgentRecord
from app.models.farm import Farm

_test_engine = create_engine(
    "sqlite:///tests/test_agent.db",
    connect_args={"check_same_thread": False},
)
event.listen(_test_engine, "connect", _set_sqlite_pragma)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    db = _TestSession()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()
    yield


@pytest.fixture
def db_session():
    session = _TestSession()
    yield session
    session.close()


class TestAgentRecord:
    """测试 AgentRecord 模型。"""

    def test_create_chat_record(self, db_session: Session) -> None:
        """验证可以创建 chat 类型记录。"""
        record = AgentRecord(
            farm_id=1,
            record_type="chat",
            content="用户对话内容",
        )
        db_session.add(record)
        db_session.commit()

        assert record.id is not None
        assert record.record_type == "chat"
        assert record.content == "用户对话内容"
        assert record.created_at is not None

    def test_create_daily_record(self, db_session: Session) -> None:
        """验证可以创建 daily 类型记录。"""
        record = AgentRecord(
            farm_id=1,
            record_type="daily",
            content="今天适合浇水",
        )
        db_session.add(record)
        db_session.commit()

        assert record.id is not None
        assert record.record_type == "daily"
        assert record.content == "今天适合浇水"

    def test_create_report_record(self, db_session: Session) -> None:
        """验证可以创建 report 类型记录。"""
        record = AgentRecord(
            farm_id=1,
            record_type="report",
            content="本周报告...",
        )
        db_session.add(record)
        db_session.commit()

        assert record.id is not None
        assert record.record_type == "report"
        assert record.content == "本周报告..."
