import pytest
from sqlalchemy.orm import Session

from app.core.database import Base, engine
from app.models.agent import AdviceRecord, ReportRecord


@pytest.fixture(autouse=True)
def clean_db():
    """每个测试前清理并重置数据库。"""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db_session():
    """提供一个数据库会话。"""
    from app.core.database import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


class TestAdviceRecord:
    """测试建议记录模型。"""

    def test_create_advice_record(self, db_session: Session) -> None:
        """验证可以创建建议记录。"""
        record = AdviceRecord(
            cycle_id=1,
            advice_type="daily",
            content="今天适合浇水",
        )
        db_session.add(record)
        db_session.commit()

        assert record.id is not None
        assert record.content == "今天适合浇水"
        assert record.created_at is not None


class TestReportRecord:
    """测试报告记录模型。"""

    def test_create_report_record(self, db_session: Session) -> None:
        """验证可以创建报告记录。"""
        record = ReportRecord(
            cycle_id=1,
            report_type="weekly",
            content="本周报告...",
        )
        db_session.add(record)
        db_session.commit()

        assert record.id is not None
        assert record.report_type == "weekly"
        assert record.content == "本周报告..."
