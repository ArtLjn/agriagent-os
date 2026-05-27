import pytest
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.models.agent_record import AgentRecord
from app.models.farm import Farm


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清理并重置数据库并播种默认农场。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(Farm(id=1, name="默认农场"))
    db.commit()
    db.close()
    yield


@pytest.fixture
def db_session():
    """提供一个数据库会话。"""
    from app.core.database import SessionLocal

    session = SessionLocal()
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
