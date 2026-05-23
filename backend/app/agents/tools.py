"""Agent 工具定义，供 LangGraph ReAct Agent 调用。

所有工具函数被 LangGraph 调用时不会传入 db Session。
需要 db 的工具在函数内部创建 SessionLocal()，使用 try/finally 确保关闭。
"""

from datetime import date, timedelta

from langchain_core.tools import tool

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.cycle import CropCycle, CycleStage
from app.models.log import FarmLog
from app.models.cost import CostRecord
from app.services.weather_service import check_weather_warnings, fetch_weather


@tool
def get_weather_forecast(location: str = "当前地块") -> str:
    """获取未来 7 天天气预报和灾害预警。

    Args:
        location: 地点描述（仅作标注，实际使用配置坐标）。

    Returns:
        格式化天气报告字符串，包含每日气温、降水、风速和预警信息。
    """
    data = fetch_weather(settings.weather_latitude, settings.weather_longitude, days=7)
    daily = data.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precips = daily.get("precipitation_sum", [])
    winds = daily.get("windspeed_10m_max", [])

    lines = [f"📍 地点：{location}", "未来 7 天天气预报："]
    for i, day in enumerate(times):
        max_t = max_temps[i] if i < len(max_temps) else "-"
        min_t = min_temps[i] if i < len(min_temps) else "-"
        p = precips[i] if i < len(precips) else "-"
        w = winds[i] if i < len(winds) else "-"
        lines.append(f"  {day}: 最高{max_t}°C 最低{min_t}°C 降水{p}mm 风速{w}m/s")

    warnings = check_weather_warnings(data)
    if warnings:
        lines.append("⚠️ 天气预警：")
        lines.extend(f"  {w}" for w in warnings)
    else:
        lines.append("✅ 近期无极端天气预警。")

    return "\n".join(lines)


@tool
def get_crop_cycle_info(cycle_id: int) -> str:
    """查询指定种植周期的详细信息，包括当前阶段和各阶段安排。

    Args:
        cycle_id: 种植周期 ID。

    Returns:
        周期详情字符串，包含名称、起止日期、当前阶段和各阶段列表。
    """
    db = SessionLocal()
    try:
        cycle = db.query(CropCycle).filter(CropCycle.id == cycle_id).first()
        if not cycle:
            return f"未找到 ID 为 {cycle_id} 的种植周期。"

        lines = [
            f"🌱 茬口：{cycle.name}",
            f"📅 开始日期：{cycle.start_date}",
            f"🗺️ 地块：{cycle.field_name or '未指定'}",
            f"📊 状态：{cycle.status}",
            "阶段安排：",
        ]
        for stage in sorted(cycle.stages, key=lambda s: s.order_index):
            current_marker = " [当前]" if stage.is_current else ""
            lines.append(
                f"  {stage.name}{current_marker}: {stage.start_date} ~ {stage.end_date} "
                f"（{stage.duration_days} 天）关键任务：{stage.key_tasks or '无'}"
            )

        return "\n".join(lines)
    finally:
        db.close()


@tool
def get_recent_farm_logs(cycle_id: int, days: int = 7) -> str:
    """查询指定周期最近 N 天的农事记录。

    Args:
        cycle_id: 种植周期 ID。
        days: 查询天数（默认 7 天）。

    Returns:
        农事记录摘要字符串，若无记录则返回提示。
    """
    db = SessionLocal()
    try:
        since = date.today() - timedelta(days=days)
        logs = (
            db.query(FarmLog)
            .filter(FarmLog.cycle_id == cycle_id, FarmLog.operation_date >= since)
            .order_by(FarmLog.operation_date.desc())
            .limit(20)
            .all()
        )

        if not logs:
            return f"最近 {days} 天内没有农事记录。"

        lines = [f"📝 最近 {days} 天农事记录（共 {len(logs)} 条）："]
        for log in logs:
            lines.append(f"  {log.operation_date}: {log.operation_type} - {log.note or '无备注'}")

        return "\n".join(lines)
    finally:
        db.close()


@tool
def get_cycle_cost_summary(cycle_id: int) -> str:
    """查询指定周期的成本与收入汇总。

    Args:
        cycle_id: 种植周期 ID。

    Returns:
        收支汇总字符串，包含总成本、总收入和净利润。
    """
    db = SessionLocal()
    try:
        records = db.query(CostRecord).filter(CostRecord.cycle_id == cycle_id).all()
        if not records:
            return "该周期暂无成本或收入记录。"

        total_cost = sum(r.amount for r in records if r.record_type == "cost")
        total_income = sum(r.amount for r in records if r.record_type == "income")
        net = total_income - total_cost

        lines = [
            f"💰 周期收支汇总：",
            f"  总成本：{total_cost} 元",
            f"  总收入：{total_income} 元",
            f"  净利润：{net} 元",
            "  明细：",
        ]
        for r in records:
            lines.append(f"    {r.record_date}: {r.record_type} - {r.category} {r.amount} 元 ({r.note or '无备注'})")

        return "\n".join(lines)
    finally:
        db.close()


__all__ = [
    "get_weather_forecast",
    "get_crop_cycle_info",
    "get_recent_farm_logs",
    "get_cycle_cost_summary",
]
