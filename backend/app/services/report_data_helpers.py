"""报告数据构造辅助函数。"""

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.models.cycle import CropCycle, CycleStage
from app.models.farm import Farm
from app.models.log import FarmLog
from app.models.planting import LaborEntry, OperationWorkOrder, Worker
from app.models.user_setting import UserSetting
from app.services.cost_service import is_legacy_repayment


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


def _build_period(report_type: str, period_start: date, period_end: date) -> dict:
    """构建统一周期信息。"""
    return {
        "granularity": "month" if report_type == "monthly" else "week",
        "start": period_start,
        "end": period_end,
        "label": f"{period_start.isoformat()} ~ {period_end.isoformat()}",
    }


def _get_previous_period(
    report_type: str, period_start: date, period_end: date
) -> tuple[date, date]:
    """计算上一自然周期。"""
    if report_type == "monthly":
        previous_month_anchor = period_start - timedelta(days=1)
        start = previous_month_anchor.replace(day=1)
        end = previous_month_anchor.replace(
            day=monthrange(previous_month_anchor.year, previous_month_anchor.month)[1]
        )
        return start, end
    period_days = (period_end - period_start).days + 1
    end = period_start - timedelta(days=1)
    start = end - timedelta(days=period_days - 1)
    return start, end


def _money_sum(values) -> Decimal:
    """合计金额，保持 Decimal 类型。"""
    return sum((value or Decimal("0") for value in values), Decimal("0"))


def _calc_progress(cycle: CropCycle) -> int:
    """计算茬口进度百分比（0-100）。"""
    stages: list[CycleStage] = sorted(cycle.stages, key=lambda s: s.order_index)
    if not stages:
        return 0
    total_duration = sum(s.duration_days for s in stages)
    if total_duration == 0:
        return 0

    current_stage_idx = -1
    for i, stage in enumerate(stages):
        if stage.is_current == 1:
            current_stage_idx = i
            break

    if current_stage_idx == -1:
        today = date.today()
        for i, stage in enumerate(stages):
            if stage.end_date >= today:
                current_stage_idx = i
                break
        if current_stage_idx == -1:
            current_stage_idx = len(stages) - 1

    completed_duration = sum(s.duration_days for s in stages[:current_stage_idx])
    current_stage = stages[current_stage_idx]
    days_in_current = max(0, (date.today() - current_stage.start_date).days)
    days_in_current = min(days_in_current, current_stage.duration_days)
    progress = (completed_duration + days_in_current) / total_duration
    return min(100, int(progress * 100))


def _get_current_stage_name(cycle: CropCycle) -> str:
    """获取茬口当前阶段名称。"""
    for stage in cycle.stages:
        if stage.is_current == 1:
            return stage.name
    today = date.today()
    stages = sorted(cycle.stages, key=lambda s: s.order_index)
    for stage in stages:
        if stage.end_date >= today:
            return stage.name
    return stages[-1].name if stages else "未知阶段"


def _get_current_stage_index(cycle: CropCycle) -> int:
    """获取当前阶段序号（1-based）。"""
    stages = sorted(cycle.stages, key=lambda s: s.order_index)
    for i, stage in enumerate(stages, start=1):
        if stage.is_current == 1:
            return i
    today = date.today()
    for i, stage in enumerate(stages, start=1):
        if stage.end_date >= today:
            return i
    return len(stages) if stages else 1


def _get_days_elapsed(cycle: CropCycle) -> int:
    """计算已种植天数。"""
    return max(0, (date.today() - cycle.start_date).days)


def _empty_labor_summary() -> dict:
    """返回空用工汇总。"""
    return {
        "entry_count": 0,
        "worker_count": 0,
        "payable_amount": "0",
        "paid_amount": "0",
        "unpaid_amount": "0",
        "labor_cost": "0",
    }


def _build_source_ref(
    source_type: str,
    source_id: int | None,
    label: str,
    occurred_on: date | None = None,
) -> dict:
    """构建统一信源引用。"""
    ref_id = f"{source_type}:{source_id}" if source_id is not None else source_type
    ref = {
        "id": ref_id,
        "source_type": source_type,
        "source_id": source_id,
        "label": label,
    }
    if occurred_on is not None:
        ref["occurred_on"] = occurred_on
    return ref


def _dedupe_source_refs(refs: list[dict]) -> list[dict]:
    """按 id 去重并保持首次出现顺序。"""
    seen = set()
    result = []
    for ref in refs:
        if ref["id"] in seen:
            continue
        seen.add(ref["id"])
        result.append(ref)
    return result


def _build_source_summary(refs: list[dict]) -> list[dict]:
    """按信源类型汇总引用数量。"""
    counts: dict[str, int] = {}
    for ref in refs:
        source_type = ref["source_type"]
        counts[source_type] = counts.get(source_type, 0) + 1
    return [
        {"source_type": source_type, "count": count}
        for source_type, count in sorted(counts.items())
    ]


def _build_work_order_items(work_orders: list[OperationWorkOrder]) -> list[dict]:
    """构建作业单事实列表。"""
    return [
        {
            "id": item.id,
            "cycle_id": item.cycle_id,
            "operation_type": item.operation_type,
            "operation_date": item.operation_date,
            "scope_type": item.scope_type,
            "note": item.note,
            "labor_entry_count": len(item.labor_entries),
        }
        for item in work_orders
    ]


def _build_labor_facts(
    labor_entries: list[LaborEntry],
) -> tuple[list[dict], list[dict], dict]:
    """构建用工明细、工人列表和汇总。"""
    worker_map: dict[int, Worker] = {}
    entry_items = []
    for entry in labor_entries:
        worker = entry.worker
        if worker is not None:
            worker_map[worker.id] = worker
        entry_items.append(
            {
                "id": entry.id,
                "work_order_id": entry.work_order_id,
                "worker_id": entry.worker_id,
                "worker_name": worker.name if worker is not None else None,
                "pay_type": entry.pay_type,
                "quantity": _format_amount(entry.quantity),
                "unit_price": _format_amount(entry.unit_price),
                "payable_amount": _format_amount(entry.payable_amount),
                "paid_amount": _format_amount(entry.paid_amount),
                "unpaid_amount": _format_amount(entry.unpaid_amount),
                "settlement_status": entry.settlement_status,
            }
        )

    payable = _money_sum(entry.payable_amount for entry in labor_entries)
    paid = _money_sum(entry.paid_amount for entry in labor_entries)
    unpaid = _money_sum(entry.unpaid_amount for entry in labor_entries)
    workers = [
        {
            "id": worker.id,
            "name": worker.name,
            "status": worker.status,
            "default_pay_type": worker.default_pay_type,
        }
        for worker in worker_map.values()
    ]
    summary = {
        "entry_count": len(labor_entries),
        "worker_count": len(worker_map),
        "payable_amount": _format_amount(payable),
        "paid_amount": _format_amount(paid),
        "unpaid_amount": _format_amount(unpaid),
        "labor_cost": _format_amount(payable),
    }
    return entry_items, workers, summary


def _query_period_costs(
    db: Session, farm_id: int, period_start: date, period_end: date
) -> list[CostRecord]:
    """查询周期内账务记录，并排除历史还款兼容记录。"""
    costs = (
        db.query(CostRecord)
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_date >= period_start,
            CostRecord.record_date <= period_end,
        )
        .order_by(CostRecord.record_date.desc(), CostRecord.id.desc())
        .all()
    )
    return [cost for cost in costs if not is_legacy_repayment(cost)]


def _calculate_base_metrics(
    costs: list[CostRecord],
    logs: list[FarmLog],
    work_orders: list[OperationWorkOrder],
    labor_summary: dict,
) -> dict:
    """计算确定性基础指标。"""
    total_cost = _money_sum(
        cost.amount for cost in costs if cost.record_type == "cost"
    )
    total_income = _money_sum(
        cost.amount for cost in costs if cost.record_type == "income"
    )
    net_profit = total_income - total_cost
    return {
        "active_cycles": 0,
        "log_count": len(logs),
        "work_order_count": len(work_orders),
        "cost_record_count": len(costs),
        "total_cost": _format_amount(total_cost),
        "total_income": _format_amount(total_income),
        "net_profit": _format_amount(net_profit),
        "labor": labor_summary,
    }


def _build_previous_period(
    db: Session,
    farm_id: int,
    report_type: str,
    period_start: date,
    period_end: date,
) -> dict:
    """构建上一自然周期对比事实。"""
    previous_start, previous_end = _get_previous_period(
        report_type, period_start, period_end
    )
    previous_logs = (
        db.query(FarmLog)
        .filter(
            FarmLog.farm_id == farm_id,
            FarmLog.operation_date >= previous_start,
            FarmLog.operation_date <= previous_end,
        )
        .all()
    )
    previous_costs = _query_period_costs(db, farm_id, previous_start, previous_end)
    previous_orders = (
        db.query(OperationWorkOrder)
        .filter(
            OperationWorkOrder.farm_id == farm_id,
            OperationWorkOrder.operation_date >= previous_start,
            OperationWorkOrder.operation_date <= previous_end,
        )
        .all()
    )
    total_cost = _money_sum(
        cost.amount for cost in previous_costs if cost.record_type == "cost"
    )
    total_income = _money_sum(
        cost.amount for cost in previous_costs if cost.record_type == "income"
    )
    return {
        "period": _build_period(report_type, previous_start, previous_end),
        "has_baseline": bool(previous_logs or previous_costs or previous_orders),
        "metrics": {
            "total_cost": _format_amount(total_cost),
            "total_income": _format_amount(total_income),
            "net_profit": _format_amount(total_income - total_cost),
            "log_count": len(previous_logs),
            "work_order_count": len(previous_orders),
        },
        "changes": {},
    }


def _resolve_weather_location(farm: Farm | None, user_setting: UserSetting | None) -> dict:
    """从农场和用户设置中解析天气定位。"""
    return {
        "location": (
            (user_setting.default_city if user_setting else None)
            or (farm.location if farm else None)
            or ""
        ),
        "lat": user_setting.default_lat if user_setting else None,
        "lon": user_setting.default_lon if user_setting else None,
    }


class ReportData:
    """报告数据的内部容器。"""

    def __init__(
        self,
        report_type: str,
        period_start: date,
        period_end: date,
        overview: dict,
        cycles: list[dict],
        costs: list[dict],
        logs: list[dict],
        period: dict | None = None,
        metrics: list[dict] | None = None,
        metric_facts: dict | None = None,
        sections: list[dict] | None = None,
        operation_work_orders: list[dict] | None = None,
        labor_entries: list[dict] | None = None,
        workers: list[dict] | None = None,
        labor_summary: dict | None = None,
        previous_period: dict | None = None,
        source_summary: dict | None = None,
        source_refs: list[dict] | None = None,
        farm: dict | None = None,
        user_settings: dict | None = None,
        weather: dict | None = None,
    ):
        self.report_type = report_type
        self.period_start = period_start
        self.period_end = period_end
        self.period = period or _build_period(report_type, period_start, period_end)
        self.overview = overview
        self.cycles = cycles
        self.costs = costs
        self.logs = logs
        self.metrics = metrics or []
        self.metric_facts = metric_facts or {}
        self.sections = sections or []
        self.operation_work_orders = operation_work_orders or []
        self.labor_entries = labor_entries or []
        self.workers = workers or []
        self.labor_summary = labor_summary or _empty_labor_summary()
        self.previous_period = previous_period
        self.source_summary = source_summary or []
        self.source_refs = source_refs or []
        self.farm = farm
        self.user_settings = user_settings
        self.weather = weather or {"available": False, "warnings": [], "error": None}

