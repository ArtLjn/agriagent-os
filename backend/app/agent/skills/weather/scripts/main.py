"""天气预报 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.config import settings
from app.core.database import SessionLocal
from app.infra.skill_cache import cached
from app.services.weather_service import check_weather_warnings, fetch_weather


def _get_user_coords(farm_id: int) -> tuple[float, float]:
    """从 user_settings 读取用户坐标，无记录时降级到默认值。"""
    default_lat = settings.weather_latitude
    default_lon = settings.weather_longitude
    try:
        db = SessionLocal()
        try:
            from app.models.farm import Farm
            from app.models.user_setting import UserSetting

            farm = db.query(Farm).filter(Farm.id == farm_id).first()
            if farm and farm.user_id:
                setting = (
                    db.query(UserSetting)
                    .filter(UserSetting.user_id == farm.user_id)
                    .first()
                )
                if setting and setting.default_lat and setting.default_lon:
                    return setting.default_lat, setting.default_lon
        finally:
            db.close()
    except Exception:
        pass
    return default_lat, default_lon


def _weather_emoji(precip: float, max_temp: float) -> str:
    """根据降水量和温度返回天气 emoji。"""
    if precip >= 20:
        return "⛈️"
    if precip >= 5:
        return "🌧️"
    if precip >= 0.5:
        return "🌦️"
    if precip == 0 and max_temp >= 25:
        return "☀️"
    if max_temp <= 5:
        return "❄️"
    return "🌤️"


def _format_date_m_d(date_str: str) -> str:
    """将 YYYY-MM-DD 转为 M/D 格式。"""
    parts = date_str.split("-")
    return f"{int(parts[1])}/{int(parts[2])}"


def _format_weather_reply(location: str, data: dict) -> str:
    """将天气数据格式化为 Markdown 表格回复。"""
    daily = data.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    precips = daily.get("precipitation_sum", [])

    if not times:
        return "🌤️ 暂时获取不到天气数据，请稍后再试。"

    count = min(3, len(times))

    lines = [f"📍 {location} · 未来 {count} 天预报", ""]
    lines.append("| 日期 | 天气 | 最高 | 最低 | 降水 |")
    lines.append("|------|------|------|------|------|")

    for i in range(count):
        day = _format_date_m_d(times[i])
        max_t = max_temps[i] if i < len(max_temps) else "-"
        min_t = min_temps[i] if i < len(min_temps) else "-"
        p = precips[i] if i < len(precips) else 0
        emoji = _weather_emoji(float(p), float(max_t) if max_t != "-" else 20)
        lines.append(f"| {day} | {emoji} | {max_t}℃ | {min_t}℃ | {p}mm |")

    warnings = check_weather_warnings(data)
    if warnings:
        lines.append("")
        for w in warnings:
            lines.append(f"⚠️ {w}")

    return "\n".join(lines)


class WeatherSkill(Skill):
    def name(self) -> str:
        return "get_weather_forecast"

    def description(self) -> str:
        return (
            "获取未来7天天气预报和灾害预警。当用户问天气怎么样、明天天气、"
            "最近有雨吗、气温多少、有没有极端天气时，调用此工具获取真实天气数据。"
        )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "地点描述（仅作标注，实际使用配置坐标）",
                    "default": "当前地块",
                },
            },
            "required": [],
        }

    @cached(ttl_seconds=1800)
    async def execute(self, params: dict, context) -> SkillResult:
        location = params.get("location", "当前地块")
        farm_id = getattr(context, "farm_id", 1) or 1
        lat, lon = _get_user_coords(farm_id)
        data = fetch_weather(lat, lon, days=3)
        reply = _format_weather_reply(location, data)
        return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
