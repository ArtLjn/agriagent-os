"""农场上下文注入层，组装农场现状摘要文本供 Agent prompt 使用。

摘要包含：活跃茬口、近期农事、未结清债务、月度成本、天气。
各类型硬上限裁剪，内存 TTL 缓存 5 分钟。
"""

import logging
import time
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.models.cost import CostRecord
from app.models.farm import Farm
from app.models.cycle import CropCycle
from app.models.log import FarmLog
from app.services import weather_service

logger = logging.getLogger(__name__)

# 摘要最大字符数
_MAX_LENGTH = 300

# 各类型硬上限
_MAX_CYCLES = 3
_MAX_LOGS = 3
_MAX_DEBTS = 3
_MAX_WEATHER_DAYS = 3

# 默认天气坐标（苏州）
_DEFAULT_LAT = 31.3
_DEFAULT_LON = 120.6


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


def build_summary(db: Session, farm_id: int) -> str:
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
    debt_line = _build_debt_line(db, farm_id)
    cost_line = _build_cost_line(db, farm_id)
    weather_line = _build_weather_line(db, farm_id)

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
        end_str = ""
        if current_stage and current_stage.end_date:
            end_str = f"(预计{current_stage.end_date.isoformat()}采收)"
        parts.append(f"{cycle.name}({stage_name}{end_str})")

    return "、".join(parts)


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
        days_ago = (date.today() - log.operation_date).days
        time_desc = _format_days_ago(days_ago)
        parts.append(f"{time_desc}{log.operation_type}")

    return "、".join(parts)


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


def _build_weather_line(db: Session, farm_id: int) -> str:
    """组装天气行，取未来 3 天。

    优先从 user_settings 读取用户坐标，无记录时降级到默认坐标。
    """
    lat, lon = _DEFAULT_LAT, _DEFAULT_LON
    try:
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        if farm and farm.user_id:
            from app.models.user_setting import UserSetting

            setting = (
                db.query(UserSetting)
                .filter(UserSetting.user_id == farm.user_id)
                .first()
            )
            if setting and setting.default_lat and setting.default_lon:
                lat, lon = setting.default_lat, setting.default_lon
    except Exception:
        logger.warning("读取用户设置失败，使用默认坐标")
    try:
        data = weather_service.fetch_weather(
            lat=lat, lon=lon, days=_MAX_WEATHER_DAYS
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
