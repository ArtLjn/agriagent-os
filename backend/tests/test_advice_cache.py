"""每日建议 v2 缓存逻辑测试。"""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.agent_record import AgentRecord
from app.services.daily_advice_models import DailyAdviceCandidate, fingerprint_candidates


def _today_start() -> datetime:
    """返回今天 00:00 本地时间（无时区信息），与 service 层一致。"""
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def _candidate(key: str, title: str = "高温错峰采收") -> DailyAdviceCandidate:
    """构造用于缓存新鲜度判断的建议候选。"""
    return DailyAdviceCandidate(
        id=key,
        category="weather",
        title_hint=title,
        detail_hint=f"{title}详情，今天最高温较高，建议错峰安排。",
        priority=2,
        due_date=None,
        source_type="weather_service",
        source_id=12,
        dedupe_key=key,
        reason="天气服务命中高温规则",
    )


def _v2_payload(candidate: DailyAdviceCandidate, *, label: str | None = None) -> dict:
    """构造合法 DailyAdvice v2 payload。"""
    title = label or candidate.title_hint
    return {
        "preview": "今日建议",
        "overview": {
            "score": 82,
            "subtitle": "今日天气偏热，请优先安排关键作业。",
            "metrics": [
                {"key": "weather", "label": "天气", "value": "高温"},
                {"key": "work_order", "label": "作业", "value": "1项"},
                {"key": "pending", "label": "待处理", "value": "0项"},
            ],
        },
        "items": [
            {
                "id": candidate.id,
                "category": candidate.category,
                "source_type": candidate.source_type,
                "source_id": candidate.source_id,
                "priority": candidate.priority,
                "compact": {
                    "title": title[:12],
                    "subtitle": "今天最高温较高，建议避开中午高温时段安排采收。",
                    "icon": "CloudSun",
                    "icon_color": "amber",
                },
                "detail_view": {
                    "title": title,
                    "description": "今天最高温较高，需要避开中午高温时段安排采收并关注人员状态。",
                    "evidence": [
                        {
                            "title": "天气依据",
                            "description": candidate.reason,
                            "source_type": candidate.source_type,
                            "source_id": candidate.source_id,
                        }
                    ],
                    "steps": [
                        {"order": 1, "title": "查看天气窗口"},
                        {"order": 2, "title": "调整采收安排"},
                    ],
                    "related": [],
                    "actions": [{"type": "ask_agent", "label": "问问芽芽"}],
                },
            }
        ],
        "generation": {
            "schema_version": "daily_advice_v2",
            "mode": "llm",
            "retry_count": 0,
            "cache_hit": False,
            "candidate_fingerprint": fingerprint_candidates([candidate]),
        },
        "created_at": "2026-06-13T08:00:00",
    }


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
        "app.services.daily_advice_generation.collect_daily_advice_candidates",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = []
        yield mock


class TestDailyAdviceCache:
    """测试 get_daily_advice v2 缓存命中/未命中逻辑。"""

    @pytest.mark.asyncio
    async def test_cache_miss_calls_llm(
        self, db, mock_composer, mock_collect_candidates
    ):
        """无 v2 缓存时应调用 LLM 并保存 v2 JSON。"""
        candidate = _candidate("weather:hot:miss")
        mock_collect_candidates.return_value = [candidate]
        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = json.dumps(_v2_payload(candidate), ensure_ascii=False)
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].id == candidate.id
        record = db.query(AgentRecord).filter(AgentRecord.record_type == "daily").one()
        assert json.loads(record.meta)["schema_version"] == "daily_advice_v2"

    @pytest.mark.asyncio
    async def test_v2_cache_hit_skips_llm(self, db, mock_collect_candidates):
        """schema version 和 candidate fingerprint 匹配时直接返回缓存。"""
        today = _today_start()
        candidate = _candidate("weather:hot:cache")
        fingerprint = fingerprint_candidates([candidate])
        payload = _v2_payload(candidate, label="缓存建议")
        payload["generation"]["candidate_fingerprint"] = fingerprint
        db.add(
            AgentRecord(
                farm_id=1,
                record_type="daily",
                content=json.dumps(payload, ensure_ascii=False),
                created_at=today,
                meta=json.dumps(
                    {
                        "schema_version": "daily_advice_v2",
                        "candidate_fingerprint": fingerprint,
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()
        mock_collect_candidates.return_value = [candidate]

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_not_called()
        assert result.items[0].title == "缓存建议"
        assert result.generation.cache_hit is True

    @pytest.mark.asyncio
    async def test_stale_candidate_fingerprint_regenerates(
        self, db, mock_composer, mock_collect_candidates
    ):
        """候选 fingerprint 变化时应忽略今日缓存并重新生成。"""
        today = _today_start()
        old_candidate = _candidate("weather:old", "旧候选")
        new_candidate = _candidate("weather:new", "新候选")
        cached_payload = _v2_payload(old_candidate)
        db.add(
            AgentRecord(
                farm_id=1,
                record_type="daily",
                content=json.dumps(cached_payload, ensure_ascii=False),
                created_at=today,
                meta=json.dumps(
                    {
                        "schema_version": "daily_advice_v2",
                        "candidate_fingerprint": fingerprint_candidates(
                            [old_candidate]
                        ),
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()
        mock_collect_candidates.return_value = [new_candidate]

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = json.dumps(
                _v2_payload(new_candidate),
                ensure_ascii=False,
            )
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].id == new_candidate.id

    @pytest.mark.asyncio
    async def test_legacy_cache_is_ignored(
        self, db, mock_composer, mock_collect_candidates
    ):
        """旧 schema 或无 schema 的缓存不能阻止 v2 重新生成。"""
        today = _today_start()
        candidate = _candidate("weather:hot:legacy")
        db.add(
            AgentRecord(
                farm_id=1,
                record_type="daily",
                content='[{"title":"结算工人欠款","detail":"旧污染缓存","priority":2}]',
                created_at=today,
                meta=json.dumps({"schema_version": "daily_advice_v1"}),
            )
        )
        db.commit()
        mock_collect_candidates.return_value = [candidate]

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = json.dumps(_v2_payload(candidate), ensure_ascii=False)
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].id == candidate.id

    @pytest.mark.asyncio
    async def test_yesterday_record_is_expired(
        self, db, mock_composer, mock_collect_candidates
    ):
        """昨天生成的缓存应已过期，需重新生成。"""
        yesterday = _today_start() - timedelta(days=1)
        old_candidate = _candidate("weather:old-day", "旧建议")
        new_candidate = _candidate("weather:new-day", "新建议")
        db.add(
            AgentRecord(
                farm_id=1,
                record_type="daily",
                content=json.dumps(_v2_payload(old_candidate), ensure_ascii=False),
                created_at=yesterday,
                meta=json.dumps(
                    {
                        "schema_version": "daily_advice_v2",
                        "candidate_fingerprint": fingerprint_candidates(
                            [old_candidate]
                        ),
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()
        mock_collect_candidates.return_value = [new_candidate]

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = json.dumps(_v2_payload(new_candidate), ensure_ascii=False)
            from app.services.agent_service import get_daily_advice

            result = await get_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].id == new_candidate.id

    @pytest.mark.asyncio
    async def test_refresh_deletes_old_and_regenerates(
        self, db, mock_composer, mock_collect_candidates
    ):
        """刷新应删除旧缓存并重新生成。"""
        today = _today_start()
        old_candidate = _candidate("weather:old-refresh", "旧缓存")
        new_candidate = _candidate("weather:new-refresh", "刷新后的建议")
        db.add(
            AgentRecord(
                farm_id=1,
                record_type="daily",
                content=json.dumps(_v2_payload(old_candidate), ensure_ascii=False),
                created_at=today,
                meta=json.dumps(
                    {
                        "schema_version": "daily_advice_v2",
                        "candidate_fingerprint": fingerprint_candidates(
                            [old_candidate]
                        ),
                    },
                    ensure_ascii=False,
                ),
            )
        )
        db.commit()
        mock_collect_candidates.return_value = [new_candidate]

        with patch(
            "app.services.agent_service.invoke_advisor", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = json.dumps(_v2_payload(new_candidate), ensure_ascii=False)
            from app.services.agent_service import refresh_daily_advice

            result = await refresh_daily_advice(db, farm_id=1)

        mock_llm.assert_called_once()
        assert result.items[0].id == new_candidate.id
        records = (
            db.query(AgentRecord)
            .filter(AgentRecord.farm_id == 1, AgentRecord.record_type == "daily")
            .all()
        )
        assert len(records) == 1
