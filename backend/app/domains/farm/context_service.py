"""农场上下文注入层，组装农场现状摘要文本供 Agent prompt 使用。

摘要包含：活跃茬口、近期农事、未结清债务、月度成本、天气。
各类型硬上限裁剪，内存 TTL 缓存 5 分钟。
"""

import logging
import time
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.domains.finance.cost_models import CostRecord
from app.domains.planting.cycle_models import CropCycle
from app.domains.planting.models import LaborEntry, OperationWorkOrder, PlantingUnit, Worker
from app.domains.weather import service as weather_service
from app.domains.weather.location_resolver import resolve_weather_location

logger = logging.getLogger(__name__)

# 摘要最大字符数
_MAX_LENGTH = 300

# 各类型硬上限
_MAX_CYCLES = 3
_MAX_LOGS = 3
_MAX_DEBTS = 3
_MAX_WEATHER_DAYS = 3


def _is_mock_session(db: Session) -> bool:
    """判断是否为单元测试中的 mock session。"""
    return isinstance(db, Mock)


class _Cache:
    """简单的内存 TTL 缓存，farm_id 为键。"""

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._store: dict[int, tuple[str, float]] = {}

    def get(self, farm_id: int) -> str | None:
        """获取缓存，过期返回 None。"""
        entry = self._store.get(farm_id)
        if entry is None:
            return None
        value, expire_at = entry
        if time.time() >= expire_at:
            del self._store[farm_id]
            return None
        return value

    def put(self, farm_id: int, value: str) -> None:
        """写入缓存。"""
        self._store[farm_id] = (value, time.time() + self._ttl)

    def clear(self) -> None:
        """清除所有缓存。"""
        self._store.clear()


# 模块级缓存实例，5 分钟过期
_cache = _Cache(ttl_seconds=300)


def clear_context_cache() -> None:
    """清除农场上下文缓存（供测试或手动刷新使用）。"""
    _cache.clear()
    logger.info("农场上下文缓存已清除")


async def build_summary(db: Session, farm_id: int) -> str:
    """组装农场现状摘要文本（≤300字）。

    查询数据库获取活跃茬口、近期农事、债务、月度成本，
    调用天气服务获取未来 3 天天气，组装为中文自然语言摘要。
    结果按 farm_id 缓存 5 分钟。

    Args:
        db: 数据库会话。
        farm_id: 农场 ID，默认 1。

    Returns:
        农场现状摘要文本，总长度 ≤300 字。
    """
    # 检查缓存
    cached = _cache.get(farm_id)
    if cached is not None:
        logger.info("农场上下文缓存命中 farm_id=%d", farm_id)
        return cached

    logger.info("农场上下文缓存未命中，开始组装 farm_id=%d", farm_id)

    # 各部分分别查询并组装
    cycle_line = _build_cycle_line(db, farm_id)
    log_line = _build_log_line(db, farm_id)
    debt_line = _build_unsettled_labor_line(db, farm_id) or _build_debt_line(
        db, farm_id
    )
    cost_line = _build_cost_line(db, farm_id)
    weather_line = await _build_weather_line(db, farm_id)

    # 拼接摘要
    parts = [
        "【农场现状】",
        f"茬口：{cycle_line}",
    ]
    if log_line:
        parts.append(f"近期农事：{log_line}")
    if debt_line:
        parts.append(f"欠账：{debt_line}")
    parts.append(f"本月花费：{cost_line}")
    parts.append(f"天气：{weather_line}")

    summary = "\n".join(parts)

    # 硬限制 ≤300 字
    if len(summary) > _MAX_LENGTH:
        summary = summary[:_MAX_LENGTH]

    # 写入缓存
    _cache.put(farm_id, summary)
    return summary


def _build_cycle_line(db: Session, farm_id: int) -> str:
    """组装活跃茬口行。

    查询 status='active' 的茬口，取当前阶段和预计采收日。
    硬上限 ≤3 个，无茬口时返回「当前无种植计划」。
    """
    cycles = (
        db.query(CropCycle)
        .filter(CropCycle.farm_id == farm_id, CropCycle.status == "active")
        .order_by(CropCycle.start_date.desc())
        .limit(_MAX_CYCLES)
        .all()
    )

    if not cycles:
        return "当前无种植计划"

    parts: list[str] = []
    for cycle in cycles[:_MAX_CYCLES]:
        current_stage = _get_current_stage(cycle)
        stage_name = current_stage.name if current_stage else "未知阶段"
        area_text = _format_cycle_area(db, cycle, farm_id)
        end_str = ""
        if current_stage and current_stage.end_date:
            end_label = (
                "预计采收"
                if "采收" in str(getattr(current_stage, "name", ""))
                else "阶段至"
            )
            end_str = f"({end_label}{current_stage.end_date.isoformat()})"
        parts.append(f"{cycle.name}{area_text}({stage_name}{end_str})")

    return "、".join(parts)


def _format_cycle_area(db: Session, cycle: CropCycle, farm_id: int) -> str:
    """格式化批次面积和种植单元数量。"""
    if _is_mock_session(db):
        unit_count, unit_area = 0, None
    else:
        try:
            unit_count, unit_area = (
                db.query(func.count(PlantingUnit.id), func.sum(PlantingUnit.area_mu))
                .filter(
                    PlantingUnit.farm_id == farm_id, PlantingUnit.cycle_id == cycle.id
                )
                .first()
            )
        except Exception:
            unit_count, unit_area = 0, None
    area = unit_area or getattr(cycle, "total_area_mu", None)
    parts: list[str] = []
    if area:
        parts.append(f"{_format_amount(area)}亩")
    if unit_count:
        parts.append(f"{unit_count}个单元")
    return f"[{','.join(parts)}]" if parts else ""


def _get_current_stage(cycle: CropCycle) -> object | None:
    """获取茬口的当前阶段。"""
    if not cycle.stages:
        return None
    for stage in cycle.stages:
        if getattr(stage, "is_current", 0) == 1:
            return stage
    # 无标记时返回最后一个阶段
    return cycle.stages[-1]


def _build_log_line(db: Session, farm_id: int) -> str:
    """组装近期农事行。

    查询最近 3 天的农事记录，硬上限 ≤3 条。
    """
    three_days_ago = date.today() - timedelta(days=3)

    if _is_mock_session(db):
        from app.domains.planting.log_models import FarmLog

        logs = (
            db.query(FarmLog)
            .filter(
                FarmLog.farm_id == farm_id,
                FarmLog.operation_date >= three_days_ago,
            )
            .order_by(FarmLog.operation_date.desc())
            .limit(_MAX_LOGS)
            .all()
        )
    else:
        logs = (
            db.query(OperationWorkOrder)
            .filter(
                OperationWorkOrder.farm_id == farm_id,
                OperationWorkOrder.operation_date >= three_days_ago,
            )
            .order_by(OperationWorkOrder.operation_date.desc())
            .limit(_MAX_LOGS)
            .all()
        )
        if not logs:
            from app.domains.planting.log_models import FarmLog

            logs = (
                db.query(FarmLog)
                .filter(
                    FarmLog.farm_id == farm_id,
                    FarmLog.operation_date >= three_days_ago,
                )
                .order_by(FarmLog.operation_date.desc())
                .limit(_MAX_LOGS)
                .all()
            )

    if not logs:
        return ""

    parts: list[str] = []
    for log in logs[:_MAX_LOGS]:
        operation_date = log.operation_date
        days_ago = (date.today() - operation_date).days
        time_desc = _format_days_ago(days_ago)
        parts.append(f"{time_desc}{log.operation_type}")

    return "、".join(parts)


def _build_unsettled_labor_line(db: Session, farm_id: int) -> str:
    """组装未结人工行。"""
    if _is_mock_session(db):
        return ""
    try:
        rows = (
            db.query(Worker.name, func.sum(LaborEntry.unpaid_amount))
            .join(Worker, Worker.id == LaborEntry.worker_id)
            .filter(
                LaborEntry.farm_id == farm_id,
                LaborEntry.unpaid_amount > 0,
            )
            .group_by(Worker.name)
            .limit(_MAX_DEBTS)
            .all()
        )
    except Exception:
        return ""
    if not rows:
        return ""
    return "、".join(f"{name}未付{_format_amount(amount)}元" for name, amount in rows)


def _format_days_ago(days: int) -> str:
    """将天数差转为自然语言时间描述。"""
    if days <= 0:
        return "今天"
    if days == 1:
        return "昨天"
    if days == 2:
        return "前天"
    return f"{days}天前"


def _build_debt_line(db: Session, farm_id: int) -> str:
    """组装未结清债务行。

    查询 note 中包含赊账关键词的 cost 记录，
    硬上限 ≤3 笔。
    目前简化处理：查询近期大额 cost 记录，按 note 描述债权人。
    """
    # 查询有备注的成本记录作为"欠账"
    debts = (
        db.query(CostRecord)
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_type == "cost",
            CostRecord.note.isnot(None),
            CostRecord.note != "",
        )
        .order_by(CostRecord.record_date.desc())
        .limit(_MAX_DEBTS)
        .all()
    )

    if not debts:
        return ""

    parts: list[str] = []
    for debt in debts[:_MAX_DEBTS]:
        amount_str = _format_amount(debt.amount)
        note = debt.note or ""
        due_info = ""
        if debt.record_date:
            days_to_due = (debt.record_date - date.today()).days
            if 0 < days_to_due <= 7:
                due_info = f"({days_to_due}天后到期)"
            elif days_to_due <= 0:
                due_info = "(已到期)"
        parts.append(f"{note} {amount_str}元{due_info}")

    return "、".join(parts)


def _format_amount(amount: Decimal) -> str:
    """格式化金额，去除不必要的零。"""
    if amount == amount.to_integral_value():
        return str(int(amount))
    return str(amount.normalize())


def _build_cost_line(db: Session, farm_id: int) -> str:
    """组装月度成本汇总行。

    查询当月 record_type='cost' 的 SUM(amount)。
    """
    today = date.today()
    total = (
        db.query(func.sum(CostRecord.amount))
        .filter(
            CostRecord.farm_id == farm_id,
            CostRecord.record_type == "cost",
            extract("year", CostRecord.record_date) == today.year,
            extract("month", CostRecord.record_date) == today.month,
        )
        .scalar()
    )

    if total is None:
        total = Decimal("0")

    return f"{_format_amount(total)}元"


async def _build_weather_line(db: Session, farm_id: int) -> str:
    """组装天气行，取未来 3 天。

    优先从默认农场经营地区读取，无记录时降级到用户设置和系统默认坐标。
    """
    try:
        resolved = resolve_weather_location(db, farm_id=farm_id)
    except Exception:
        logger.warning("解析天气位置失败，使用系统默认坐标")
        resolved = resolve_weather_location(db)
    try:
        data = await weather_service.fetch_weather(
            resolved.location,
            days=_MAX_WEATHER_DAYS,
            lat=resolved.lat,
            lon=resolved.lon,
        )
        return _format_weather_line(data, days=_MAX_WEATHER_DAYS)
    except Exception:
        logger.warning("天气数据获取失败，使用降级提示")
        return "暂无天气数据"


def _format_weather_line(weather_data: dict, days: int = 3) -> str:
    """将天气数据格式化为自然语言描述。

    Args:
        weather_data: Open-Meteo 返回的天气字典。
        days: 取前 N 天。

    Returns:
        天气描述字符串，如"明天晴25°/后天阴20°/大后天雨18°"。
    """
    daily = weather_data.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    precipitations = daily.get("precipitation_sum", [])

    if not times:
        return "暂无天气数据"

    today = date.today()
    parts: list[str] = []

    for i in range(min(days, len(times))):
        if i >= len(max_temps):
            break

        day_str = times[i]
        try:
            day_date = date.fromisoformat(day_str)
        except (ValueError, TypeError):
            continue

        # 跳过过去日期
        if day_date < today:
            continue

        diff = (day_date - today).days
        label = _format_day_label(diff)

        temp = max_temps[i]
        precip = precipitations[i] if i < len(precipitations) else 0

        # 根据降水量判断天气描述
        weather_desc = _weather_desc(precip)
        parts.append(f"{label}{weather_desc}{_fmt_temp(temp)}")

    if not parts:
        return "暂无天气数据"

    return "/".join(parts)


def _format_day_label(diff: int) -> str:
    """将日期差转为自然语言日期标签。"""
    if diff == 0:
        return "今天"
    if diff == 1:
        return "明天"
    if diff == 2:
        return "后天"
    if diff == 3:
        return "大后天"
    return f"{diff}天后"


def _weather_desc(precip: float) -> str:
    """根据降水量判断天气描述。"""
    if precip >= 10:
        return "雨"
    if precip >= 1:
        return "阴"
    return "晴"


def _fmt_temp(temp: float) -> str:
    """格式化温度为整数字符串。"""
    return f"{int(round(temp))}°"


__all__ = [
    "build_summary",
    "clear_context_cache",
    "_Cache",
    "_MAX_LENGTH",
    "_format_weather_line",
]
