"""报告数据查询服务。

按时间范围精确查询周报/月报所需的结构化数据，
关键指标由数据库直接计算，不依赖 LLM。
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.models.cycle import CropCycle, CycleStage
from app.models.log import FarmLog
from app.services.cost_service import is_legacy_repayment

logger = logging.getLogger(__name__)


def _get_week_range(today: date | None = None) -> tuple[date, date]:
    """计算本周一和本周日。"""
    today = today or date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def _get_month_range(today: date | None = None) -> tuple[date, date]:
    """计算本月第一天和最后一天。"""
    today = today or date.today()
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    month_end = next_month - timedelta(days=1)
    return month_start, month_end


def _format_amount(amount: Decimal) -> str:
    """格式化金额，去除不必要的零。"""
    if amount == amount.to_integral_value():
        return str(int(amount))
    return str(amount.normalize())


def _calc_progress(cycle: CropCycle) -> int:
    """计算茬口进度百分比（0-100）。

    基于已完成阶段的 duration 占总 duration 的比例。
    """
    stages: list[CycleStage] = sorted(cycle.stages, key=lambda s: s.order_index)
    if not stages:
        return 0

    total_duration = sum(s.duration_days for s in stages)
    if total_duration == 0:
        return 0

    # 找到当前阶段
    current_stage_idx = -1
    for i, s in enumerate(stages):
        if s.is_current == 1:
            current_stage_idx = i
            break

    if current_stage_idx == -1:
        # 无标记，按日期推断：找到第一个 end_date >= today 的阶段
        today = date.today()
        for i, s in enumerate(stages):
            if s.end_date >= today:
                current_stage_idx = i
                break
        if current_stage_idx == -1:
            current_stage_idx = len(stages) - 1

    # 已完成阶段的 duration 之和
    completed_duration = sum(s.duration_days for s in stages[:current_stage_idx])

    # 当前阶段已进行天数
    current_stage = stages[current_stage_idx]
    days_in_current = max(0, (date.today() - current_stage.start_date).days)
    days_in_current = min(days_in_current, current_stage.duration_days)

    progress = (completed_duration + days_in_current) / total_duration
    return min(100, int(progress * 100))


def _get_current_stage_name(cycle: CropCycle) -> str:
    """获取茬口当前阶段名称。"""
    for s in cycle.stages:
        if s.is_current == 1:
            return s.name
    # fallback: 按日期推断
    today = date.today()
    stages = sorted(cycle.stages, key=lambda s: s.order_index)
    for s in stages:
        if s.end_date >= today:
            return s.name
    return stages[-1].name if stages else "未知阶段"


def _get_current_stage_index(cycle: CropCycle) -> int:
    """获取当前阶段序号（1-based）。"""
    stages = sorted(cycle.stages, key=lambda s: s.order_index)
    for i, s in enumerate(stages, start=1):
        if s.is_current == 1:
            return i
    today = date.today()
    for i, s in enumerate(stages, start=1):
        if s.end_date >= today:
            return i
    return len(stages) if stages else 1


def _get_days_elapsed(cycle: CropCycle) -> int:
    """计算已种植天数。"""
    return max(0, (date.today() - cycle.start_date).days)


class ReportData:
    """报告数据的内部容器（用 dataclass 太冗余，直接用 dict-like）。"""

    def __init__(
        self,
        report_type: str,
        period_start: date,
        period_end: date,
        overview: dict,
        cycles: list[dict],
        costs: list[dict],
        logs: list[dict],
    ):
        self.report_type = report_type
        self.period_start = period_start
        self.period_end = period_end
        self.overview = overview
        self.cycles = cycles
        self.costs = costs
        self.logs = logs


def _build_report_data(
    db: Session,
    farm_id: int,
    period_start: date,
    period_end: date,
    report_type: str,
) -> ReportData:
    """构建指定时间范围内的报告数据。"""

    # 1. 活跃茬口
    cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .all()
    )

    # 2. 本周期农事记录
    logs = (
        db.query(FarmLog)
        .filter(
            FarmLog.farm_id == farm_id,
            FarmLog.operation_date >= period_start,
            FarmLog.operation_date <= period_end,
        )
        .order_by(FarmLog.operation_date.desc())
        .all()
    )

    # 3. 本周期成本记录
    costs = (
        db.query(CostRecord)
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_date >= period_start,
            CostRecord.record_date <= period_end,
        )
        .order_by(CostRecord.record_date.desc())
        .all()
    )
    costs = [cost for cost in costs if not is_legacy_repayment(cost)]

    # 4. 计算概览指标
    total_cost = sum(
        (cost.amount for cost in costs if cost.record_type == "cost"),
        Decimal("0"),
    )
    total_income = sum(
        (cost.amount for cost in costs if cost.record_type == "income"),
        Decimal("0"),
    )

    net_profit = total_income - total_cost

    # 5. 构建茬口详情列表
    cycle_items = []
    for c in cycles:
        # 该茬口本周期内的农事数
        cycle_log_count = sum(1 for log in logs if log.cycle_id == c.id)
        stages = sorted(c.stages, key=lambda s: s.order_index)
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
            }
        )

    # 6. 构建成本明细列表
    cost_items = [
        {
            "cycle_id": c.cycle_id,
            "category": c.category,
            "amount": _format_amount(c.amount),
            "record_type": c.record_type,
            "record_date": c.record_date,
            "note": c.note,
        }
        for c in costs
    ]

    # 7. 构建农事记录列表
    log_items = []
    cycle_name_map = {c.id: c.name for c in cycles}
    for log in logs:
        log_items.append(
            {
                "cycle_id": log.cycle_id,
                "operation_type": log.operation_type,
                "operation_date": log.operation_date,
                "note": log.note,
                "cycle_name": cycle_name_map.get(log.cycle_id),
            }
        )

    overview = {
        "active_cycles": len(cycles),
        "log_count": len(logs),
        "total_cost": _format_amount(total_cost),
        "total_income": _format_amount(total_income),
        "net_profit": _format_amount(net_profit),
    }

    logger.info(
        "报告数据构建完成 | type=%s farm=%s cycles=%d logs=%d costs=%d",
        report_type,
        farm_id,
        len(cycles),
        len(logs),
        len(costs),
    )

    return ReportData(
        report_type=report_type,
        period_start=period_start,
        period_end=period_end,
        overview=overview,
        cycles=cycle_items,
        costs=cost_items,
        logs=log_items,
    )


async def get_weekly_report_data(db: Session, farm_id: int) -> ReportData:
    """获取本周报告数据。"""
    week_start, week_end = _get_week_range()
    return _build_report_data(db, farm_id, week_start, week_end, "weekly")


async def get_monthly_report_data(db: Session, farm_id: int) -> ReportData:
    """获取本月报告数据。"""
    month_start, month_end = _get_month_range()
    return _build_report_data(db, farm_id, month_start, month_end, "monthly")


__all__ = [
    "get_weekly_report_data",
    "get_monthly_report_data",
    "ReportData",
]
