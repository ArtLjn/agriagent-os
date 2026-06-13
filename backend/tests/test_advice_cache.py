"""每日建议缓存逻辑测试。"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.agent_record import AgentRecord
from app.services.daily_advice_models import (
    DailyAdviceCandidate,
    fingerprint_candidates,
)


def _today_start() -> datetime:
    """返回今天 00:00 本地时间（无时区信息），与 service 层一致。"""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _json_items_response(label: str) -> str:
    """构造合法 JSON 数组 LLM 返回值。"""
    return f'[{{"title":"{label}","detail":"{label}详情","priority":1,"icon":"📋"}}]'


def _candidate(key: str, title: str) -> DailyAdviceCandidate:
    """构造用于缓存新鲜度判断的建议候选。"""
    return DailyAdviceCandidate(
        id=key,
        category="operation",
        title_hint=title,
        detail_hint=f"{title}详情",
        priority=1,
        due_date=None,
        source_type="test",
        source_id=None,
        dedupe_key=key,
        reason="缓存测试",
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


@pytest.fixture
def mock_composer():
    """隔离 prompt 渲染，缓存测试只关注命中/未命中行为。"""
    with patch("app.services.agent_service.get_composer") as mock:
        mock.return_value.compose.return_value = "daily prompt"
        yield mock


@pytest.fixture(autouse=True)
def mock_collect_candidates():
    """缓存测试默认不依赖真实候选采集。"""
    with patch(
        "app.services.agent_service.collect_daily_advice_candidates",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = []
        yield mock


class TestDailyAdviceCache:
    """测试 get_daily_advice 缓存命中/未命中逻辑。"""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm(self, db, mock_composer):
        """无缓存时应调用 LLM。"""
        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _json_items_response("建议内容")
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].title == "建议内容"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_llm(self, db):
        """有缓存时不应调用 LLM，直接返回缓存。"""
        today = _today_start()
        cached_json = _json_items_response("缓存建议")
        cached = AgentRecord(
            farm_id=1,
            record_type="daily",
            content=cached_json,
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
        assert result.items[0].title == "缓存建议"

    @pytest.mark.asyncio
    async def test_cache_with_stale_candidate_fingerprint_regenerates(
        self, db, mock_composer, mock_collect_candidates
    ):
        """候选 fingerprint 变化时应忽略今日缓存并重新生成。"""
        today = _today_start()
        old_candidate = _candidate("operation:old", "旧候选")
        new_candidate = _candidate("operation:new", "新候选")
        cached = AgentRecord(
            farm_id=1,
            record_type="daily",
            content=_json_items_response("旧缓存"),
            created_at=today,
            meta=json.dumps(
                {
                    "selected_candidates": [old_candidate.to_meta()],
                    "candidate_fingerprint": fingerprint_candidates([old_candidate]),
                },
                ensure_ascii=False,
            ),
        )
        db.add(cached)
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_collect_candidates.return_value = [new_candidate]
            mock_llm.return_value = _json_items_response("新建议")
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].title == "新建议"

    @pytest.mark.asyncio
    async def test_legacy_debt_advice_cache_is_ignored(self, db, mock_composer):
        """旧缓存里若含未结人工建议，应重新生成而不是继续命中。"""
        today = _today_start()
        cached = AgentRecord(
            farm_id=1,
            record_type="daily",
            content=(
                '[{"title":"结算工人欠款","detail":"诸葛四郎、李海、朱7'
                '三人各有100元未付，建议尽快安排支付","priority":2,"icon":"💰"}]'
            ),
            created_at=today,
        )
        db.add(cached)
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _json_items_response("重新生成")
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].title == "重新生成"

    @pytest.mark.asyncio
    async def test_quota_reject_message_cache_is_ignored(self, db, mock_composer):
        """身份/配额拦截文案不应作为每日建议缓存复用。"""
        today = _today_start()
        cached = AgentRecord(
            farm_id=1,
            record_type="daily",
            content="缺少可信用户上下文，无法继续处理。",
            created_at=today,
        )
        db.add(cached)
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _json_items_response("重新生成")
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].title == "重新生成"

    @pytest.mark.asyncio
    async def test_different_farm_cache_miss(self, db, mock_composer):
        """不同 farm_id 应视为缓存未命中。"""
        today = _today_start()
        db.add(
            AgentRecord(
                farm_id=1,
                record_type="daily",
                content=_json_items_response("农场1"),
                created_at=today,
            )
        )
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _json_items_response("农场2建议")
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=2)

        mock_llm.assert_called_once()
        assert result.items[0].title == "农场2建议"

    @pytest.mark.asyncio
    async def test_yesterday_record_is_expired(self, db, mock_composer):
        """昨天生成的缓存应已过期，需重新生成。"""
        yesterday = _today_start() - timedelta(days=1)
        db.add(
            AgentRecord(
                farm_id=1,
                record_type="daily",
                content=_json_items_response("旧建议"),
                created_at=yesterday,
            )
        )
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _json_items_response("新建议")
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].title == "新建议"

    @pytest.mark.asyncio
    async def test_refresh_deletes_old_and_regenerates(self, db, mock_composer):
        """刷新应删除旧缓存并重新生成。"""
        today = _today_start()
        db.add(
            AgentRecord(
                farm_id=1,
                record_type="daily",
                content=_json_items_response("旧缓存"),
                created_at=today,
            )
        )
        db.commit()

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = _json_items_response("刷新后的建议")
            from app.services.agent_service import refresh_daily_advice

            result = await refresh_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].title == "刷新后的建议"
        records = (
            db.query(AgentRecord)
            .filter(AgentRecord.farm_id == 1, AgentRecord.record_type == "daily")
            .all()
        )
        assert len(records) == 1
        assert "刷新后的建议" in records[0].content
