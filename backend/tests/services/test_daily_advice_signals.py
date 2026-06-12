"""Daily advice signal pipeline tests."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

from app.models.cost import CostRecord
from app.models.crop import CropTemplate
from app.models.cycle import CropCycle, CycleStage
from app.models.planting import OperationWorkOrder
from app.services.daily_advice_models import (
    DailyAdviceCandidate,
    DailyAdviceCategory,
    rank_daily_advice_candidates,
    render_candidate_context,
)
from app.services.daily_advice_signals import collect_daily_advice_candidates


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


def _weather_data(
    *,
    temps: list[float],
    times: list[str] | None = None,
    rain: list[float] | None = None,
    wind: list[float] | None = None,
) -> dict:
    days = len(temps)
    return {
        "daily": {
            "time": times or [f"2026-06-{12 + index:02d}" for index in range(days)],
            "temperature_2m_max": temps,
            "precipitation_sum": rain or [0] * days,
            "windspeed_10m_max": wind or [0] * days,
        }
    }


def _create_active_cycle(
    db_session,
    *,
    today: date,
    crop_name: str = "西瓜",
    cycle_name: str = "早春西瓜一茬",
    stage_name: str = "伸蔓期",
    key_tasks: str | None = "巡田、理蔓",
) -> CropCycle:
    template = CropTemplate(farm_id=1, name=crop_name)
    db_session.add(template)
    db_session.flush()
    cycle = CropCycle(
        farm_id=1,
        name=cycle_name,
        crop_template_id=template.id,
        start_date=today - timedelta(days=5),
        status="active",
    )
    db_session.add(cycle)
    db_session.flush()
    stage = CycleStage(
        cycle_id=cycle.id,
        name=stage_name,
        start_date=today - timedelta(days=3),
        end_date=today + timedelta(days=7),
        order_index=1,
        duration_days=11,
        key_tasks=key_tasks,
        is_current=True,
    )
    db_session.add(stage)
    db_session.commit()
    return cycle


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


async def test_collect_finance_candidates_skips_debt_without_due_date_and_labor_debt(
    db_session,
):
    today = date(2026, 6, 12)
    debt_without_due_date = CostRecord(
        farm_id=1,
        record_type="cost",
        category="农资",
        amount=Decimal("300.00"),
        settled_amount=Decimal("0.00"),
        record_date=today,
        record_subtype="赊账",
        counterparty="农资店",
    )
    labor_debt = CostRecord(
        farm_id=1,
        record_type="cost",
        category="人工",
        amount=Decimal("180.00"),
        settled_amount=Decimal("0.00"),
        record_date=today,
        record_subtype="工资记录人工",
        due_date=today,
        counterparty="张师傅",
    )
    db_session.add_all([debt_without_due_date, labor_debt])
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)
    finance_candidates = [item for item in candidates if item.category == "finance"]

    assert finance_candidates == []


async def test_collect_finance_candidates_includes_overdue_and_due_soon_debts(
    db_session,
):
    today = date(2026, 6, 12)
    overdue_debt = CostRecord(
        farm_id=1,
        record_type="cost",
        category="农资",
        amount=Decimal("300.00"),
        settled_amount=Decimal("0.00"),
        record_date=today - timedelta(days=7),
        record_subtype="赊账",
        due_date=today - timedelta(days=1),
        counterparty="老李农资",
    )
    due_soon_debt = CostRecord(
        farm_id=1,
        record_type="cost",
        category="肥料",
        amount=Decimal("500.00"),
        settled_amount=Decimal("200.00"),
        record_date=today,
        record_subtype="赊账",
        due_date=today + timedelta(days=3),
        counterparty="肥料供应商",
    )
    later_debt = CostRecord(
        farm_id=1,
        record_type="cost",
        category="农资",
        amount=Decimal("600.00"),
        settled_amount=Decimal("0.00"),
        record_date=today,
        record_subtype="赊账",
        due_date=today + timedelta(days=4),
        counterparty="下周供应商",
    )
    settled_debt = CostRecord(
        farm_id=1,
        record_type="cost",
        category="农资",
        amount=Decimal("100.00"),
        settled_amount=Decimal("100.00"),
        record_date=today,
        record_subtype="赊账",
        due_date=today,
        counterparty="已结供应商",
    )
    db_session.add_all([overdue_debt, due_soon_debt, later_debt, settled_debt])
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)
    finance_candidates = [item for item in candidates if item.category == "finance"]

    assert [item.source_id for item in finance_candidates] == [
        overdue_debt.id,
        due_soon_debt.id,
    ]
    assert [item.priority for item in finance_candidates] == [1, 2]
    assert finance_candidates[0].title_hint == "赊账已逾期"
    assert "老李农资" in finance_candidates[0].detail_hint
    assert "300.00" in finance_candidates[0].detail_hint
    assert finance_candidates[1].title_hint == "赊账即将到期"
    assert "300.00" in finance_candidates[1].detail_hint


async def test_collect_operation_candidates_includes_overdue_today_and_next_three_days(
    db_session,
):
    today = date(2026, 6, 12)
    overdue_order = OperationWorkOrder(
        farm_id=1,
        operation_type="补肥",
        operation_date=today - timedelta(days=1),
        scope_type="farm",
        note="逾期作业",
    )
    today_order = OperationWorkOrder(
        farm_id=1,
        operation_type="巡田",
        operation_date=today,
        scope_type="farm",
    )
    tomorrow_order = OperationWorkOrder(
        farm_id=1,
        operation_type="打药",
        operation_date=today + timedelta(days=1),
        scope_type="farm",
    )
    two_days_order = OperationWorkOrder(
        farm_id=1,
        operation_type="浇水",
        operation_date=today + timedelta(days=2),
        scope_type="farm",
    )
    three_days_order = OperationWorkOrder(
        farm_id=1,
        operation_type="采收",
        operation_date=today + timedelta(days=3),
        scope_type="farm",
    )
    later_order = OperationWorkOrder(
        farm_id=1,
        operation_type="整地",
        operation_date=today + timedelta(days=4),
        scope_type="farm",
    )
    db_session.add_all(
        [
            overdue_order,
            today_order,
            tomorrow_order,
            two_days_order,
            three_days_order,
            later_order,
        ]
    )
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)
    operation_candidates = [item for item in candidates if item.category == "operation"]

    assert [item.source_id for item in operation_candidates] == [
        overdue_order.id,
        today_order.id,
        tomorrow_order.id,
        two_days_order.id,
        three_days_order.id,
    ]
    assert [item.priority for item in operation_candidates] == [1, 1, 1, 2, 2]
    assert operation_candidates[0].title_hint == "补肥作业已逾期"
    assert operation_candidates[1].title_hint == "今日安排巡田"
    assert operation_candidates[2].title_hint == "明日安排打药"
    assert operation_candidates[3].title_hint == "近期安排浇水"
    assert operation_candidates[4].title_hint == "近期安排采收"


async def test_collect_weather_candidates_includes_high_temperature_p1(
    db_session,
    monkeypatch,
):
    today = date(2026, 6, 12)
    fetch_weather = AsyncMock(return_value=_weather_data(temps=[36, 32, 31]))
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        fetch_weather,
    )

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)
    weather_candidates = [item for item in candidates if item.category == "weather"]

    fetch_weather.assert_awaited_once_with(days=3)
    assert len(weather_candidates) == 1
    assert weather_candidates[0].priority == 1
    assert weather_candidates[0].source_type == "weather_service"
    assert weather_candidates[0].due_date == today
    assert "高温" in weather_candidates[0].title_hint


async def test_collect_weather_candidates_merges_continuous_high_temperature(
    db_session,
    monkeypatch,
):
    today = date(2026, 6, 12)
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        AsyncMock(return_value=_weather_data(temps=[35, 36, 37])),
    )

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)
    weather_candidates = [item for item in candidates if item.category == "weather"]

    assert len(weather_candidates) == 1
    assert "持续高温" in weather_candidates[0].detail_hint


async def test_collect_weather_candidates_ignores_expired_hot_days(
    db_session,
    monkeypatch,
):
    today = date(2026, 6, 12)
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        AsyncMock(
            return_value=_weather_data(
                times=["2026-06-14", "2026-06-11", "2026-06-13"],
                temps=[36, 39, 31],
            )
        ),
    )

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)
    weather_candidates = [item for item in candidates if item.category == "weather"]

    assert len(weather_candidates) == 1
    assert "2026-06-14" in weather_candidates[0].detail_hint
    assert "2026-06-11" not in weather_candidates[0].detail_hint


async def test_collect_weather_candidates_checks_future_third_day_after_expired_prefix(
    db_session,
    monkeypatch,
):
    today = date(2026, 6, 12)
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        AsyncMock(
            return_value=_weather_data(
                times=["2026-06-11", "2026-06-12", "2026-06-13", "2026-06-15"],
                temps=[39, 30, 31, 36],
            )
        ),
    )

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)
    weather_candidates = [item for item in candidates if item.category == "weather"]

    assert len(weather_candidates) == 1
    assert "2026-06-15" in weather_candidates[0].detail_hint
    assert "2026-06-11" not in weather_candidates[0].detail_hint


async def test_collect_crop_stage_candidates_from_current_active_cycle(
    db_session,
    monkeypatch,
):
    today = date(2026, 6, 12)
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        AsyncMock(return_value=_weather_data(temps=[30, 31, 32])),
    )
    cycle = _create_active_cycle(db_session, today=today)

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)
    crop_stage_candidates = [
        item for item in candidates if item.category == "crop_stage"
    ]

    assert len(crop_stage_candidates) == 1
    assert crop_stage_candidates[0].priority == 2
    assert crop_stage_candidates[0].source_id == cycle.id
    assert crop_stage_candidates[0].source_type == "crop_cycle"
    assert "西瓜" in crop_stage_candidates[0].detail_hint
    assert "早春西瓜一茬" in crop_stage_candidates[0].detail_hint
    assert "伸蔓期" in crop_stage_candidates[0].detail_hint


async def test_collect_crop_stage_candidates_suppresses_recent_same_operation(
    db_session,
    monkeypatch,
):
    today = date(2026, 6, 12)
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        AsyncMock(return_value=_weather_data(temps=[30, 31, 32])),
    )
    cycle = _create_active_cycle(db_session, today=today, key_tasks="巡田、理蔓")
    db_session.add(
        OperationWorkOrder(
            farm_id=1,
            cycle_id=cycle.id,
            operation_type="巡田",
            operation_date=today - timedelta(days=1),
            scope_type="cycle",
        )
    )
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)

    assert [
        item for item in candidates if item.category == "crop_stage"
    ] == []


async def test_collect_crop_stage_candidates_suppresses_by_cycle_only(
    db_session,
    monkeypatch,
):
    today = date(2026, 6, 12)
    monkeypatch.setattr(
        "app.services.daily_advice_signals.weather_service.fetch_weather",
        AsyncMock(return_value=_weather_data(temps=[30, 31, 32])),
    )
    cycle_a = _create_active_cycle(
        db_session,
        today=today,
        crop_name="西瓜",
        cycle_name="西瓜一茬",
        key_tasks="巡田、理蔓",
    )
    cycle_b = _create_active_cycle(
        db_session,
        today=today,
        crop_name="番茄",
        cycle_name="番茄一茬",
        key_tasks="巡田、绑蔓",
    )
    db_session.add(
        OperationWorkOrder(
            farm_id=1,
            cycle_id=cycle_a.id,
            operation_type="巡田",
            operation_date=today - timedelta(days=1),
            scope_type="cycle",
        )
    )
    db_session.commit()

    candidates = await collect_daily_advice_candidates(db_session, farm_id=1, today=today)
    crop_stage_candidates = [
        item for item in candidates if item.category == "crop_stage"
    ]

    assert [item.source_id for item in crop_stage_candidates] == [cycle_b.id]
    assert "番茄一茬" in crop_stage_candidates[0].detail_hint
