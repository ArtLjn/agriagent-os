"""每日建议缓存逻辑测试。"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.agent import AdviceRecord


def _today_start() -> datetime:
    """返回今天 00:00 CST 对应的 UTC 时间（无时区信息）。"""
    cst = timezone(timedelta(hours=8))
    now = datetime.now(cst)
    return (
        now.replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )


@pytest.fixture
def db():
    """提供独立的内存 SQLite 会话。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestDailyAdviceCache:
    """测试 get_daily_advice 缓存命中/未命中逻辑。"""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm(self, db):
        """无缓存时应调用 LLM。"""
        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "建议内容"
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.advice == "建议内容"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, db):
        """有缓存时不应调用 LLM，直接返回缓存。"""
        today = _today_start()
        cached = AdviceRecord(
            farm_id=1,
            advice_type="daily",
            content="缓存建议",
            created_at=today,
        )
        db.add(cached)
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_not_called()
        assert result.advice == "缓存建议"

    @pytest.mark.asyncio
    async def test_different_farm_cache_miss(self, db):
        """不同 farm_id 应视为缓存未命中。"""
        today = _today_start()
        db.add(
            AdviceRecord(
                farm_id=1, advice_type="daily", content="农场1", created_at=today
            )
        )
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "农场2建议"
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=2)

        mock_llm.assert_called_once()
        assert result.advice == "农场2建议"

    @pytest.mark.asyncio
    async def test_yesterday_record_is_expired(self, db):
        """昨天生成的缓存应已过期，需重新生成。"""
        yesterday = _today_start() - timedelta(days=1)
        db.add(
            AdviceRecord(
                farm_id=1,
                advice_type="daily",
                content="旧建议",
                created_at=yesterday,
            )
        )
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "新建议"
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.advice == "新建议"

    @pytest.mark.asyncio
    async def test_refresh_deletes_old_and_regenerates(self, db):
        """刷新应删除旧缓存并重新生成。"""
        today = _today_start()
        db.add(
            AdviceRecord(
                farm_id=1,
                advice_type="daily",
                content="旧缓存",
                created_at=today,
            )
        )
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "刷新后的建议"
            from app.services.agent_service import refresh_daily_advice

            result = await refresh_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.advice == "刷新后的建议"
        records = (
            db.query(AdviceRecord)
            .filter(AdviceRecord.farm_id == 1, AdviceRecord.advice_type == "daily")
            .all()
        )
        assert len(records) == 1
        assert records[0].content == "刷新后的建议"
