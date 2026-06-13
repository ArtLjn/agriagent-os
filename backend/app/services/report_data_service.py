"""报告数据查询服务。

按时间范围精确查询周报/月报所需的结构化数据，
关键指标由数据库直接计算，不依赖 LLM。
"""

import logging
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.cycle import CropCycle
from app.models.farm import Farm
from app.models.log import FarmLog
from app.models.planting import LaborEntry, OperationWorkOrder, Worker
from app.models.user_setting import UserSetting
from app.services import weather_service
from app.services.report_data_helpers import (
    ReportData,
    _build_period,
    _build_previous_period,
    _build_source_ref,
    _build_source_summary,
    _build_work_order_items,
    _calculate_base_metrics,
    _calc_progress,
    _dedupe_source_refs,
    _format_amount,
    _get_current_stage_index,
    _get_current_stage_name,
    _get_days_elapsed,
    _get_month_range,
    _get_week_range,
    _query_period_costs,
    _resolve_weather_location,
    _build_labor_facts,
)
from app.services.report_sections import build_report_sections, metric_items

logger = logging.getLogger(__name__)


def _build_report_data(
    db: Session,
    farm_id: int,
    period_start: date,
    period_end: date,
    report_type: str,
) -> ReportData:
    """构建指定时间范围内的报告数据。

    兼容旧同步调用，不主动访问天气外部服务。
    """
    return _build_report_data_core(
        db=db,
        farm_id=farm_id,
        period_start=period_start,
        period_end=period_end,
        report_type=report_type,
        weather=None,
    )


async def build_report_data_for_period(
    db: Session,
    farm_id: int,
    period_start: date,
    period_end: date,
    report_type: str,
) -> ReportData:
    """为指定自然周期构建完整报告事实。"""
    partial = _build_report_data_core(
        db=db,
        farm_id=farm_id,
        period_start=period_start,
        period_end=period_end,
        report_type=report_type,
        weather=None,
    )
    partial.weather = await _fetch_weather_fact(partial.farm, partial.user_settings)
    if partial.weather["available"]:
        partial.source_refs = _dedupe_source_refs(
            partial.source_refs
            + [_build_source_ref("weather_service", None, "天气服务未来风险")]
        )
        partial.source_summary = _build_source_summary(partial.source_refs)
    partial.sections = build_report_sections(
        partial.report_type,
        metric_facts=partial.metric_facts,
        cycles=partial.cycles,
        costs=partial.costs,
        logs=partial.logs,
        work_orders=partial.operation_work_orders,
        labor_summary=partial.labor_summary,
        previous_period=partial.previous_period,
        weather=partial.weather,
        source_refs=partial.source_refs,
    )
    return partial

def _build_report_data_core(
    *,
    db: Session,
    farm_id: int,
    period_start: date,
    period_end: date,
    report_type: str,
    weather: dict | None,
) -> ReportData:
    """构建报告事实，不包含外部天气调用。"""
    farm = db.query(Farm).filter(Farm.id == farm_id).first()
    user_setting = None
    if farm and farm.user_id:
        user_setting = (
            db.query(UserSetting).filter(UserSetting.user_id == farm.user_id).first()
        )
    cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .all()
    )
    logs = (
        db.query(FarmLog)
        .filter(
            FarmLog.farm_id == farm_id,
            FarmLog.operation_date >= period_start,
            FarmLog.operation_date <= period_end,
        )
        .order_by(FarmLog.operation_date.desc(), FarmLog.id.desc())
        .all()
    )
    costs = _query_period_costs(db, farm_id, period_start, period_end)
    work_orders = (
        db.query(OperationWorkOrder)
        .filter(
            OperationWorkOrder.farm_id == farm_id,
            OperationWorkOrder.operation_date >= period_start,
            OperationWorkOrder.operation_date <= period_end,
        )
        .order_by(OperationWorkOrder.operation_date.desc(), OperationWorkOrder.id.desc())
        .all()
    )
    labor_entries = (
        db.query(LaborEntry)
        .join(OperationWorkOrder, OperationWorkOrder.id == LaborEntry.work_order_id)
        .join(Worker, Worker.id == LaborEntry.worker_id)
        .filter(
            LaborEntry.farm_id == farm_id,
            OperationWorkOrder.farm_id == farm_id,
            OperationWorkOrder.operation_date >= period_start,
            OperationWorkOrder.operation_date <= period_end,
        )
        .order_by(OperationWorkOrder.operation_date.desc(), LaborEntry.id.desc())
        .all()
    )
    labor_items, worker_items, labor_summary = _build_labor_facts(labor_entries)

    total_cost = sum(
        (cost.amount for cost in costs if cost.record_type == "cost"),
        Decimal("0"),
    )
    total_income = sum(
        (cost.amount for cost in costs if cost.record_type == "income"),
        Decimal("0"),
    )

    net_profit = total_income - total_cost

    cycle_items = []
    source_refs = []
    if farm is not None:
        source_refs.append(_build_source_ref("farm", farm.id, farm.name))
    if user_setting is not None:
        source_refs.append(
            _build_source_ref("user_setting", user_setting.id, "用户报告偏好")
        )

    for c in cycles:
        cycle_log_count = sum(1 for log in logs if log.cycle_id == c.id)
        stages = sorted(c.stages, key=lambda s: s.order_index)
        cycle_source_refs = []
        cycle_ref = _build_source_ref("crop_cycle", c.id, c.name, c.start_date)
        source_refs.append(cycle_ref)
        cycle_source_refs.append(cycle_ref["id"])
        for stage in stages:
            stage_ref = _build_source_ref(
                "cycle_stage", stage.id, stage.name, stage.start_date
            )
            source_refs.append(stage_ref)
            cycle_source_refs.append(stage_ref["id"])
        cycle_items.append(
            {
                "cycle_id": c.id,
                "name": c.name,
                "field_name": c.field_name,
                "current_stage": _get_current_stage_name(c),
                "progress_percent": _calc_progress(c),
                "period_log_count": cycle_log_count,
                "total_stages": len(stages),
                "current_stage_index": _get_current_stage_index(c),
                "days_elapsed": _get_days_elapsed(c),
                "source_ref_ids": cycle_source_refs,
            }
        )

    cost_items = [
        {
            "id": c.id,
            "cycle_id": c.cycle_id,
            "category": c.category,
            "amount": _format_amount(c.amount),
            "record_type": c.record_type,
            "record_date": c.record_date,
            "note": c.note,
        }
        for c in costs
    ]
    source_refs.extend(
        _build_source_ref(
            "cost_record",
            c.id,
            f"{c.category} {c.record_type} {_format_amount(c.amount)}元",
            c.record_date,
        )
        for c in costs
    )

    log_items = []
    cycle_name_map = {c.id: c.name for c in cycles}
    for log in logs:
        source_refs.append(
            _build_source_ref(
                "farm_log", log.id, log.operation_type, log.operation_date
            )
        )
        log_items.append(
            {
                "id": log.id,
                "cycle_id": log.cycle_id,
                "operation_type": log.operation_type,
                "operation_date": log.operation_date,
                "note": log.note,
                "cycle_name": cycle_name_map.get(log.cycle_id),
            }
        )

    work_order_items = _build_work_order_items(work_orders)
    source_refs.extend(
        _build_source_ref(
            "operation_work_order",
            order.id,
            order.operation_type,
            order.operation_date,
        )
        for order in work_orders
    )
    source_refs.extend(
        _build_source_ref("labor_entry", entry.id, "用工记录", entry.work_order.operation_date)
        for entry in labor_entries
    )
    source_refs.extend(
        _build_source_ref("worker", worker["id"], worker["name"]) for worker in worker_items
    )

    overview = {
        "active_cycles": len(cycles),
        "log_count": len(logs),
        "total_cost": _format_amount(total_cost),
        "total_income": _format_amount(total_income),
        "net_profit": _format_amount(net_profit),
    }
    metrics = _calculate_base_metrics(costs, logs, work_orders, labor_summary)
    metrics["active_cycles"] = len(cycles)
    previous_period = _build_previous_period(
        db, farm_id, report_type, period_start, period_end
    )

    logger.info(
        "报告数据构建完成 | type=%s farm=%s cycles=%d logs=%d costs=%d orders=%d labor=%d",
        report_type,
        farm_id,
        len(cycles),
        len(logs),
        len(costs),
        len(work_orders),
        len(labor_entries),
    )

    source_refs = _dedupe_source_refs(source_refs)
    return ReportData(
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        overview=overview,
        cycles=cycle_items,
        costs=cost_items,
        logs=log_items,
        period=_build_period(report_type, period_start, period_end),
        metrics=metric_items(metrics),
        metric_facts=metrics,
        sections=build_report_sections(
            report_type,
            metric_facts=metrics,
            cycles=cycle_items,
            costs=cost_items,
            logs=log_items,
            work_orders=work_order_items,
            labor_summary=labor_summary,
            previous_period=previous_period,
            weather=weather or {"available": False, "warnings": [], "error": None},
            source_refs=source_refs,
        ),
        operation_work_orders=work_order_items,
        labor_entries=labor_items,
        workers=worker_items,
        labor_summary=labor_summary,
        previous_period=previous_period,
        source_summary=_build_source_summary(source_refs),
        source_refs=source_refs,
        farm=(
            {"id": farm.id, "name": farm.name, "location": farm.location}
            if farm is not None
            else None
        ),
        user_settings=(
            {
                "id": user_setting.id,
                "user_id": user_setting.user_id,
                "default_city": user_setting.default_city,
                "default_lat": user_setting.default_lat,
                "default_lon": user_setting.default_lon,
            }
            if user_setting is not None
            else None
        ),
        weather=weather,
    )


async def _fetch_weather_fact(
    farm: dict | None, user_settings: dict | None
) -> dict:
    """获取可选天气风险，失败时返回 unavailable。"""
    setting_obj = None
    if user_settings is not None:
        setting_obj = type("UserSettingFact", (), user_settings)
    farm_obj = type("FarmFact", (), farm) if farm is not None else None
    location = _resolve_weather_location(farm_obj, setting_obj)
    try:
        weather = await weather_service.fetch_weather(
            location=location["location"],
            days=7,
            lat=location["lat"],
            lon=location["lon"],
        )
        warnings = weather_service.check_weather_warnings(weather)
        return {
            "available": True,
            "warnings": warnings,
            "provider": weather.get("provider"),
            "location": weather.get("location"),
            "error": None,
        }
    except Exception as exc:
        logger.warning("报告天气信源不可用，继续生成报告 | error=%s", exc)
        return {
            "available": False,
            "warnings": [],
            "provider": None,
            "location": location["location"],
            "error": str(exc),
        }


async def get_weekly_report_data(db: Session, farm_id: int) -> ReportData:
    """获取本周报告数据。"""
    week_start, week_end = _get_week_range()
    return await build_report_data_for_period(db, farm_id, week_start, week_end, "weekly")


async def get_monthly_report_data(db: Session, farm_id: int) -> ReportData:
    """获取本月报告数据。"""
    month_start, month_end = _get_month_range()
    return await build_report_data_for_period(
        db, farm_id, month_start, month_end, "monthly"
    )


__all__ = [
    "get_weekly_report_data",
    "get_monthly_report_data",
    "ReportData",
]
