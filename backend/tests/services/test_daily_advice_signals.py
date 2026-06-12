"""Daily advice signal pipeline tests."""

from datetime import date, timedelta

from app.services.daily_advice_signals import (
    DailyAdviceCandidate,
    DailyAdviceCategory,
    rank_daily_advice_candidates,
    render_candidate_context,
)


def _candidate(
    *,
    key: str,
    category: DailyAdviceCategory,
    priority: int,
    due_date: date | None = None,
    title: str = "候选建议",
    detail: str = "候选详情",
) -> DailyAdviceCandidate:
    return DailyAdviceCandidate(
        id=key,
        category=category,
        title_hint=title,
        detail_hint=detail,
        priority=priority,
        due_date=due_date,
        source_type="test",
        source_id=None,
        dedupe_key=key,
        reason="测试原因",
    )


def test_rank_keeps_p1_before_p2_and_limits_homepage_to_three():
    today = date.today()
    candidates = [
        _candidate(key="p3", category="setup", priority=3, title="补记录"),
        _candidate(key="p2", category="operation", priority=2, title="明天作业"),
        _candidate(key="p1", category="weather", priority=1, title="高温预警"),
        _candidate(key="p2b", category="crop_stage", priority=2, title="巡田"),
    ]

    ranked = rank_daily_advice_candidates(candidates, today=today, limit=3)

    assert [item.id for item in ranked] == ["p1", "p2", "p2b"]


def test_rank_limits_weather_and_finance_categories():
    today = date.today()
    candidates = [
        _candidate(key="weather-1", category="weather", priority=1, title="高温"),
        _candidate(key="weather-2", category="weather", priority=1, title="暴雨"),
        _candidate(key="finance-1", category="finance", priority=1, title="逾期账款"),
        _candidate(key="finance-2", category="finance", priority=2, title="临期账款"),
        _candidate(key="operation-1", category="operation", priority=2, title="采收"),
    ]

    ranked = rank_daily_advice_candidates(candidates, today=today, limit=5)

    assert [item.id for item in ranked] == [
        "weather-1",
        "finance-1",
        "operation-1",
    ]


def test_rank_deduplicates_by_dedupe_key():
    today = date.today()
    candidates = [
        _candidate(key="hot-1", category="weather", priority=1, title="今天高温"),
        DailyAdviceCandidate(
            id="hot-2",
            category="weather",
            title_hint="明天高温",
            detail_hint="连续高温",
            priority=1,
            due_date=today + timedelta(days=1),
            source_type="weather",
            source_id=None,
            dedupe_key="weather:heat",
            reason="重复天气",
        ),
    ]
    candidates[0].dedupe_key = "weather:heat"

    ranked = rank_daily_advice_candidates(candidates, today=today, limit=5)

    assert len(ranked) == 1
    assert ranked[0].id == "hot-2"


def test_rank_places_candidates_with_due_date_before_without_due_date():
    today = date.today()
    candidates = [
        _candidate(key="none-due", category="operation", priority=1),
        _candidate(
            key="has-due",
            category="operation",
            priority=1,
            due_date=today + timedelta(days=3),
        ),
    ]

    ranked = rank_daily_advice_candidates(candidates, today=today, limit=2)

    assert [item.id for item in ranked] == ["has-due", "none-due"]


def test_render_candidate_context_contains_only_ranked_candidates():
    today = date.today()
    candidates = [
        DailyAdviceCandidate(
            id="weather",
            category="weather",
            title_hint="高温错峰采收",
            detail_hint="今天最高温 36 度，避开中午高温时段",
            priority=1,
            due_date=today,
            source_type="weather",
            source_id=None,
            dedupe_key="weather",
            reason="测试原因",
        ),
        _candidate(
            key="operation",
            category="operation",
            priority=2,
            due_date=today + timedelta(days=2),
            title="安排巡田",
            detail="未来 3 天进入伸蔓期，检查水肥",
        ),
    ]

    context = render_candidate_context(candidates)

    assert "高温错峰采收" in context
    assert "安排巡田" in context
    assert "priority=1" in context
    assert "source=weather" in context


def test_render_candidate_context_uses_source_type_instead_of_category():
    candidate = DailyAdviceCandidate(
        id="weather-service",
        category="weather",
        title_hint="高温错峰采收",
        detail_hint="避开中午高温时段",
        priority=1,
        due_date=None,
        source_type="weather_service",
        source_id=12,
        dedupe_key="weather:service",
        reason="天气服务命中高温规则",
    )

    context = render_candidate_context([candidate])

    assert "source=weather_service" in context
    assert "source=weather " not in context
