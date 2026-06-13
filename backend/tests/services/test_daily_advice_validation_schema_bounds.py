"""每日建议 validator 与响应 schema 边界一致性测试。"""

from datetime import date

from app.schemas.agent import DailyAdviceResponse
from app.services.daily_advice_models import DailyAdviceCandidate
from app.services.daily_advice_validation import validate_daily_advice_payload


def _candidate() -> DailyAdviceCandidate:
    return DailyAdviceCandidate(
        id="weather-1",
        category="weather",
        title_hint="高温错峰采收",
        detail_hint="今天最高温 36 度，建议避开中午高温时段安排采收。",
        priority=2,
        due_date=date(2026, 6, 13),
        source_type="weather_service",
        source_id=12,
        dedupe_key="weather:weather-1",
        reason="天气服务命中高温规则",
    )


def _payload(candidate: DailyAdviceCandidate) -> dict:
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
                    "title": "高温错峰采收",
                    "subtitle": "今天最高温较高，建议避开中午高温时段安排采收。",
                },
                "detail_view": {
                    "title": "高温错峰采收",
                    "description": "今天最高温较高，需要避开中午高温时段安排采收并关注人员状态。",
                    "evidence": [
                        {
                            "title": "天气依据",
                            "description": "天气服务命中高温规则",
                            "source_type": candidate.source_type,
                            "source_id": candidate.source_id,
                        }
                    ],
                    "steps": [
                        {"order": 1, "title": "查看天气窗口"},
                        {"order": 2, "title": "调整采收安排"},
                    ],
                    "actions": [{"type": "ask_agent", "label": "问问芽芽"}],
                },
            }
        ],
        "generation": {"schema_version": "daily_advice_v2", "mode": "llm"},
        "created_at": "2026-06-13T08:00:00",
    }


def test_text_bounds_match_response_schema_limits() -> None:
    candidate = _candidate()
    payload = _payload(candidate)
    payload["items"][0]["compact"]["title"] = "超过十二个字的首页标题会失败"
    payload["items"][0]["compact"]["subtitle"] = "过长" * 26
    payload["items"][0]["detail_view"]["description"] = "过长描述" * 31

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "daily_advice_content_too_thin"
    reasons = result.issues[0].evidence["reasons"]
    assert {reason["field"] for reason in reasons} == {
        "items[0].compact.title",
        "items[0].compact.subtitle",
        "items[0].detail_view.description",
    }


def test_validator_passed_payload_can_build_response_schema() -> None:
    candidate = _candidate()
    payload = _payload(candidate)

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is True
    response = DailyAdviceResponse.model_validate(payload)
    assert response.items[0].compact.title == "高温错峰采收"


def test_blank_or_raw_over_limit_title_fails() -> None:
    candidate = _candidate()
    blank_payload = _payload(candidate)
    blank_payload["items"][0]["compact"]["title"] = "   "
    spaced_payload = _payload(candidate)
    spaced_payload["items"][0]["compact"]["title"] = "123456789012 "

    for payload in (blank_payload, spaced_payload):
        result = validate_daily_advice_payload(payload, [candidate])

        assert result.valid is False
        assert result.issues[0].code == "daily_advice_content_too_thin"
        assert result.issues[0].evidence["reasons"][0]["field"] == (
            "items[0].compact.title"
        )


def test_missing_detail_title_fails_before_response_schema() -> None:
    candidate = _candidate()
    payload = _payload(candidate)
    del payload["items"][0]["detail_view"]["title"]

    result = validate_daily_advice_payload(payload, [candidate])

    assert result.valid is False
    assert result.issues[0].code == "daily_advice_content_too_thin"
    assert result.issues[0].evidence["reasons"][0]["field"] == (
        "items[0].detail_view.title"
    )
