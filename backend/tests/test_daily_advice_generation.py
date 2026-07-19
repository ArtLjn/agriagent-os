"""每日建议 v2 生成、重试与 fallback 测试。"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.shared.database import Base
from app.models.agent_record import AgentRecord
from app.services.daily_advice_models import DailyAdviceCandidate, fingerprint_candidates


def _candidate(key: str, title: str = "高温错峰采收") -> DailyAdviceCandidate:
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


def _v2_payload(candidate: DailyAdviceCandidate) -> dict:
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
                    "title": candidate.title_hint[:12],
                    "subtitle": "今天最高温较高，建议避开中午高温时段安排采收。",
                    "icon": "CloudSun",
                    "icon_color": "amber",
                },
                "detail_view": {
                    "title": candidate.title_hint,
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
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def mock_composer():
    with patch("app.services.agent_service.get_composer") as mock:
        mock.return_value.compose.return_value = "daily prompt"
        yield mock


@pytest.fixture(autouse=True)
def mock_collect_candidates():
    with patch(
        "app.services.daily_advice_generation.collect_daily_advice_candidates",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = []
        yield mock


@pytest.mark.asyncio
async def test_retry_success_reuses_candidates_and_records_meta(
    db,
    mock_composer,
    mock_collect_candidates,
) -> None:
    """首次校验失败后重试成功，应复用同一批候选并记录 repaired 元数据。"""
    candidate = _candidate("weather:hot:1")
    mock_collect_candidates.return_value = [candidate]
    valid_payload = _v2_payload(candidate)

    with patch(
        "app.services.agent_service.invoke_daily_advice_llm", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.side_effect = [
            '{"preview":"今日建议","items":[]}',
            json.dumps(valid_payload, ensure_ascii=False),
        ]
        from app.services.agent_service import get_daily_advice

        result = await get_daily_advice(db, farm_id=1)

    assert mock_collect_candidates.await_count == 1
    assert mock_llm.await_count == 2
    assert result.generation.mode == "repaired"
    assert result.generation.retry_count == 1
    assert result.generation.candidate_fingerprint == fingerprint_candidates(
        [candidate]
    )
    saved_record = db.query(AgentRecord).filter(AgentRecord.record_type == "daily").one()
    saved_meta = json.loads(saved_record.meta)
    assert saved_meta["schema_version"] == "daily_advice_v2"
    assert saved_meta["generation_mode"] == "repaired"
    assert saved_meta["retry_count"] == 1
    assert saved_meta["reflection_decision"] == "pass"
    assert saved_meta["validation_errors"]
    assert saved_meta["selected_candidates"][0]["id"] == candidate.id


@pytest.mark.asyncio
async def test_json_parse_failure_adds_repair_instruction_before_retry(
    db,
    mock_composer,
    mock_collect_candidates,
) -> None:
    """JSON 解析失败后，下一轮 prompt 应明确要求只返回合法 JSON。"""
    candidate = _candidate("weather:storm:1", title="暴雨前抢收排水")
    mock_collect_candidates.return_value = [candidate]
    valid_payload = _v2_payload(candidate)
    malformed_payload = (
        '{"preview": "暴雨将至，抓紧收割与排水", 我发现今日建议这个接口频繁报错'
    )

    with patch(
        "app.services.agent_service.invoke_daily_advice_llm", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.side_effect = [
            malformed_payload,
            json.dumps(valid_payload, ensure_ascii=False),
        ]
        from app.services.agent_service import get_daily_advice

        result = await get_daily_advice(db, farm_id=1)

    assert result.generation.mode == "repaired"
    assert mock_llm.await_count == 2
    first_variables = mock_composer.return_value.compose.call_args_list[0].kwargs[
        "variables"
    ]
    retry_variables = mock_composer.return_value.compose.call_args_list[1].kwargs[
        "variables"
    ]
    assert first_variables["repair_instruction"] == ""
    assert "只返回合法 JSON" in retry_variables["repair_instruction"]
    assert "不要输出解释" in retry_variables["repair_instruction"]
    saved_record = db.query(AgentRecord).filter(AgentRecord.record_type == "daily").one()
    saved_meta = json.loads(saved_record.meta)
    assert "llm_json_parse_failed" in saved_meta["validation_errors"]


@pytest.mark.asyncio
async def test_truncated_daily_advice_json_falls_back_without_retry(
    db,
    mock_composer,
    mock_collect_candidates,
) -> None:
    """明显被截断的 JSON 应快速 fallback，避免重复触发长耗时失败。"""
    candidate = _candidate("weather:storm:truncated", title="暴雨前抢收排水")
    mock_collect_candidates.return_value = [candidate]
    truncated_payload = (
        '{\n'
        '  "preview": "今日强降雨，抓紧收割水稻与催芽",\n'
        '  "overview": {\n'
        '    "score": 55,\n'
        '    "subtitle": "今日有强降雨，需防涝并处理逾期作'
    )

    with patch(
        "app.services.agent_service.invoke_daily_advice_llm", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.return_value = truncated_payload
        from app.services.agent_service import get_daily_advice

        result = await get_daily_advice(db, farm_id=1)

    assert mock_llm.await_count == 1
    assert result.generation.mode == "fallback"
    assert result.items[0].id == candidate.id
    saved_record = db.query(AgentRecord).filter(AgentRecord.record_type == "daily").one()
    saved_meta = json.loads(saved_record.meta)
    assert saved_meta["retry_count"] == 0
    assert "llm_json_truncated" in saved_meta["validation_errors"]


@pytest.mark.asyncio
async def test_retry_exhausted_returns_candidate_fallback(
    db,
    mock_composer,
    mock_collect_candidates,
) -> None:
    """三次生成都不通过时，应返回候选 skeleton fallback 并缓存完整 v2 JSON。"""
    candidate = _candidate("weather:hot:2")
    mock_collect_candidates.return_value = [candidate]

    with patch(
        "app.services.agent_service.invoke_daily_advice_llm", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.return_value = '{"preview":"今日建议","items":[]}'
        from app.services.agent_service import get_daily_advice

        result = await get_daily_advice(db, farm_id=1)

    assert mock_llm.await_count == 3
    assert result.generation.mode == "fallback"
    assert result.items[0].id == candidate.id
    saved_record = db.query(AgentRecord).filter(AgentRecord.record_type == "daily").one()
    saved_content = json.loads(saved_record.content)
    saved_meta = json.loads(saved_record.meta)
    assert saved_content["generation"]["mode"] == "fallback"
    assert saved_meta["generation_mode"] == "fallback"
    assert saved_meta["retry_count"] == 2
    assert "empty_daily_advice_items" in saved_meta["validation_errors"]


@pytest.mark.asyncio
async def test_empty_candidates_return_empty_without_llm(
    db,
    mock_collect_candidates,
) -> None:
    """没有候选时应返回 empty 模式，不调用 LLM。"""
    mock_collect_candidates.return_value = []

    with patch(
        "app.services.agent_service.invoke_daily_advice_llm", new_callable=AsyncMock
    ) as mock_llm:
        from app.services.agent_service import get_daily_advice

        result = await get_daily_advice(db, farm_id=1)

    mock_llm.assert_not_called()
    assert result.generation.mode == "empty"
    assert result.items[0].id == "empty-today"
    assert result.created_at <= datetime.now()


@pytest.mark.asyncio
async def test_quota_like_llm_response_retries_then_fallback(
    db,
    mock_composer,
    mock_collect_candidates,
) -> None:
    """配额/错误文案不能作为 raw advice 缓存，应重试后 fallback。"""
    candidate = _candidate("weather:hot:quota")
    mock_collect_candidates.return_value = [candidate]

    with patch(
        "app.services.agent_service.invoke_daily_advice_llm", new_callable=AsyncMock
    ) as mock_llm:
        mock_llm.return_value = "缺少可信用户上下文，无法继续处理。"
        from app.services.agent_service import get_daily_advice

        result = await get_daily_advice(db, farm_id=1)

    assert mock_llm.await_count == 3
    assert result.generation.mode == "fallback"
    saved_record = db.query(AgentRecord).filter(AgentRecord.record_type == "daily").one()
    assert "缺少可信用户上下文" not in saved_record.content
