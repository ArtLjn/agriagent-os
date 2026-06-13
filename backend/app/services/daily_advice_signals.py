"""今日建议候选信号收集管线。"""

from __future__ import annotations

from datetime import date
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.models.cycle import CropCycle
from app.models.planting import OperationWorkOrder
from app.services import weather_service
from app.services.daily_advice_models import DailyAdviceCandidate
from app.services.daily_advice_models import DailyAdviceCategory
from app.services.daily_advice_models import fingerprint_candidates
from app.services.daily_advice_models import rank_daily_advice_candidates
from app.services.daily_advice_models import render_candidate_context
from app.services.location_resolver import resolve_weather_location

__all__ = [
    "DailyAdviceCandidate",
    "DailyAdviceCategory",
    "collect_daily_advice_candidates",
    "fingerprint_candidates",
    "rank_daily_advice_candidates",
    "render_candidate_context",
]


async def collect_daily_advice_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date | None = None,
) -> list[DailyAdviceCandidate]:
    """收集今日建议候选信号。"""
    reference_day = today or date.today()
    recent_operation_types = _recent_operation_types(
        db,
        farm_id=farm_id,
        today=reference_day,
    )
    return [
        *await _collect_weather_candidates(
            db,
            farm_id=farm_id,
            today=reference_day,
        ),
        *_collect_crop_stage_candidates(
            db,
            farm_id=farm_id,
            today=reference_day,
            recent_operation_types=recent_operation_types,
        ),
        *_collect_operation_candidates(db, farm_id=farm_id, today=reference_day),
        *_collect_finance_candidates(db, farm_id=farm_id, today=reference_day),
    ]


async def _collect_weather_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date,
) -> list[DailyAdviceCandidate]:
    resolved = resolve_weather_location(db, farm_id=farm_id)
    try:
        weather = await weather_service.fetch_weather(
            resolved.location,
            days=3,
            lat=resolved.lat,
            lon=resolved.lon,
        )
    except Exception:
        return []

    return _weather_candidates_from_payload(weather, today=today)


def _weather_candidates_from_payload(
    weather: dict,
    *,
    today: date,
) -> list[DailyAdviceCandidate]:
    daily = weather.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    precipitations = daily.get("precipitation_sum", [])
    winds = daily.get("windspeed_10m_max", [])

    hot_days = _weather_hits(times, max_temps, threshold=35, today=today)
    if hot_days:
        return [
            _weather_candidate(
                kind="heat",
                title="高温天气注意错峰作业",
                detail=_weather_detail("高温", hot_days, "持续高温"),
                priority=1,
                today=today,
                reason="未来 3 天最高温达到 35 度及以上",
            )
        ]

    rain_days = _weather_hits(times, precipitations, threshold=10, today=today)
    if rain_days:
        return [
            _weather_candidate(
                kind="rain",
                title="明显降雨注意排水防涝",
                detail=_weather_detail("降雨", rain_days, "持续明显降雨"),
                priority=1,
                today=today,
                reason="未来 3 天降雨量达到 10 毫米及以上",
            )
        ]

    wind_days = _weather_hits(times, winds, threshold=17, today=today)
    if wind_days:
        return [
            _weather_candidate(
                kind="wind",
                title="大风天气注意设施加固",
                detail=_weather_detail("大风", wind_days, "持续大风"),
                priority=1,
                today=today,
                reason="未来 3 天最大风速达到 17 米每秒及以上",
            )
        ]

    return []


def _collect_crop_stage_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date,
    recent_operation_types: dict[int | None, set[str]],
) -> list[DailyAdviceCandidate]:
    cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .order_by(CropCycle.start_date.asc(), CropCycle.id.asc())
        .all()
    )
    if not cycles:
        return [
            DailyAdviceCandidate(
                id=f"setup:crop_cycle:{farm_id}",
                category="setup",
                title_hint="补充当前茬口信息",
                detail_hint="当前农场还没有活跃茬口，建议先建立作物和茬口阶段。",
                priority=3,
                due_date=None,
                source_type="crop_cycle",
                source_id=None,
                dedupe_key=f"setup:crop_cycle:{farm_id}",
                reason="缺少活跃茬口，无法根据生长阶段生成建议",
            )
        ]

    candidates: list[DailyAdviceCandidate] = []
    for cycle in cycles:
        stage = _current_stage(cycle)
        if stage is None:
            continue

        task = _first_stage_task(stage.key_tasks or "巡田观察")
        if task in recent_operation_types.get(cycle.id, set()):
            continue

        crop_name = cycle.crop_template.name if cycle.crop_template else "未知作物"
        candidates.append(
            DailyAdviceCandidate(
                id=f"crop_stage:cycle:{cycle.id}:stage:{stage.id}",
                category="crop_stage",
                title_hint=f"{stage.name}建议{task}",
                detail_hint=(
                    f"{crop_name}茬口「{cycle.name}」当前处于{stage.name}，"
                    f"关键任务：{stage.key_tasks or '巡田观察'}。"
                ),
                priority=2,
                due_date=today,
                source_type="crop_cycle",
                source_id=cycle.id,
                dedupe_key=f"crop_stage:{cycle.id}:{stage.id}:{task}",
                reason="当前活跃茬口阶段存在关键农事任务",
            )
        )

    return candidates


def _collect_operation_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date,
) -> list[DailyAdviceCandidate]:
    horizon = today + timedelta(days=3)
    work_orders = (
        db.query(OperationWorkOrder)
        .filter(
            OperationWorkOrder.farm_id == farm_id,
            OperationWorkOrder.operation_date <= horizon,
        )
        .order_by(OperationWorkOrder.operation_date.asc(), OperationWorkOrder.id.asc())
        .all()
    )

    candidates: list[DailyAdviceCandidate] = []
    for work_order in work_orders:
        day_offset = (work_order.operation_date - today).days
        priority = 1 if day_offset <= 1 else 2
        title = _operation_title(work_order.operation_type, day_offset)
        candidates.append(
            DailyAdviceCandidate(
                id=f"operation:work_order:{work_order.id}",
                category="operation",
                title_hint=title,
                detail_hint=_operation_detail(work_order, day_offset),
                priority=priority,
                due_date=work_order.operation_date,
                source_type="operation_work_order",
                source_id=work_order.id,
                dedupe_key=f"operation_work_order:{work_order.id}",
                reason="作业单日期进入今日建议窗口",
            )
        )

    return candidates


def _collect_finance_candidates(
    db: Session,
    *,
    farm_id: int,
    today: date,
) -> list[DailyAdviceCandidate]:
    horizon = today + timedelta(days=3)
    debts = (
        db.query(CostRecord)
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_subtype == "赊账",
            CostRecord.due_date.isnot(None),
            CostRecord.due_date <= horizon,
            CostRecord.settled_amount < CostRecord.amount,
            CostRecord.deleted_at.is_(None),
        )
        .order_by(CostRecord.due_date.asc(), CostRecord.id.asc())
        .all()
    )

    candidates: list[DailyAdviceCandidate] = []
    for debt in debts:
        day_offset = (debt.due_date - today).days
        overdue = day_offset < 0
        candidates.append(
            DailyAdviceCandidate(
                id=f"finance:cost_record:{debt.id}",
                category="finance",
                title_hint="赊账已逾期" if overdue else "赊账即将到期",
                detail_hint=_finance_detail(debt, day_offset),
                priority=1 if overdue else 2,
                due_date=debt.due_date,
                source_type="cost_record",
                source_id=debt.id,
                dedupe_key=f"finance:cost_record:{debt.id}",
                reason="赊账到期日进入今日建议窗口且尚未结清",
            )
        )

    return candidates


def _recent_operation_types(
    db: Session,
    *,
    farm_id: int,
    today: date,
) -> dict[int | None, set[str]]:
    since = today - timedelta(days=3)
    rows = (
        db.query(OperationWorkOrder.cycle_id, OperationWorkOrder.operation_type)
        .filter(
            OperationWorkOrder.farm_id == farm_id,
            OperationWorkOrder.operation_date >= since,
            OperationWorkOrder.operation_date <= today,
        )
        .all()
    )
    operation_types: dict[int | None, set[str]] = {}
    for cycle_id, operation_type in rows:
        operation_types.setdefault(cycle_id, set()).add(operation_type)
    return operation_types


def _weather_hits(
    times: list[Any],
    values: list[Any],
    *,
    threshold: float,
    today: date,
) -> list[tuple[str, float]]:
    horizon = today + timedelta(days=3)
    hits: list[tuple[str, float]] = []
    for index, raw_value in enumerate(values):
        day = _parse_weather_day(times[index] if index < len(times) else None)
        if day is None or not today <= day <= horizon:
            continue

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue

        if value >= threshold:
            hits.append((day.isoformat(), value))

    return hits


def _parse_weather_day(raw_day: Any) -> date | None:
    if isinstance(raw_day, date):
        return raw_day
    if not raw_day:
        return None
    try:
        return date.fromisoformat(str(raw_day)[:10])
    except ValueError:
        return None


def _weather_candidate(
    *,
    kind: str,
    title: str,
    detail: str,
    priority: int,
    today: date,
    reason: str,
) -> DailyAdviceCandidate:
    return DailyAdviceCandidate(
        id=f"weather:{kind}",
        category="weather",
        title_hint=title,
        detail_hint=detail,
        priority=priority,
        due_date=today,
        source_type="weather_service",
        source_id=None,
        dedupe_key=f"weather:{kind}",
        reason=reason,
    )


def _weather_detail(
    label: str,
    hits: list[tuple[str, float]],
    continuous_text: str,
) -> str:
    day_values = "、".join(f"{day} {value:g}" for day, value in hits)
    if len(hits) > 1:
        return f"未来 3 天{continuous_text}：{day_values}。"
    return f"未来 3 天有{label}风险：{day_values}。"


def _current_stage(cycle: CropCycle) -> Any | None:
    stages = sorted(cycle.stages, key=lambda stage: stage.order_index)
    if not stages:
        return None

    current = next((stage for stage in stages if stage.is_current), None)
    return current or stages[-1]


def _first_stage_task(key_tasks: str) -> str:
    for separator in ("、", "，", ",", "；", ";", "\n"):
        key_tasks = key_tasks.replace(separator, " ")
    return key_tasks.split()[0] if key_tasks.split() else "巡田观察"


def _operation_title(operation_type: str, day_offset: int) -> str:
    if day_offset < 0:
        return f"{operation_type}作业已逾期"
    if day_offset == 0:
        return f"今日安排{operation_type}"
    if day_offset == 1:
        return f"明日安排{operation_type}"
    return f"近期安排{operation_type}"


def _operation_detail(work_order: OperationWorkOrder, day_offset: int) -> str:
    if day_offset < 0:
        time_text = f"已逾期 {abs(day_offset)} 天"
    elif day_offset == 0:
        time_text = "今天到期"
    else:
        time_text = f"{day_offset} 天后到期"

    note = f"，备注：{work_order.note}" if work_order.note else ""
    return f"{work_order.operation_date.isoformat()} {work_order.operation_type}，{time_text}{note}"


def _finance_detail(debt: CostRecord, day_offset: int) -> str:
    counterparty = debt.counterparty or "未标注对象"
    if day_offset < 0:
        time_text = f"已逾期 {abs(day_offset)} 天"
    elif day_offset == 0:
        time_text = "今天到期"
    else:
        time_text = f"{day_offset} 天后到期"

    return (
        f"{counterparty} 赊账未结 {_money(debt.unsettled_amount)} 元，"
        f"到期日 {debt.due_date.isoformat()}，{time_text}"
    )


def _money(value: Decimal | int | float | str | None) -> str:
    amount = Decimal(str(value or "0")).quantize(Decimal("0.01"))
    return f"{amount:.2f}"
