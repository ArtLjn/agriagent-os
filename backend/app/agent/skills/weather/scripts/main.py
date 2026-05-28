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
        data = fetch_weather(lat, lon, days=7)
        daily = data.get("daily", {})
        times = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precips = daily.get("precipitation_sum", [])
        winds = daily.get("windspeed_10m_max", [])

        lines = [f"地点：{location}", "未来 7 天天气预报："]
        for i, day in enumerate(times):
            max_t = max_temps[i] if i < len(max_temps) else "-"
            min_t = min_temps[i] if i < len(min_temps) else "-"
            p = precips[i] if i < len(precips) else "-"
            w = winds[i] if i < len(winds) else "-"
            lines.append(f"  {day}: 最高{max_t}C 最低{min_t}C 降水{p}mm 风速{w}m/s")

        warnings = check_weather_warnings(data)
        if warnings:
            lines.append("天气预警：")
            lines.extend(f"  {w}" for w in warnings)
        else:
            lines.append("近期无极端天气预警。")

        return SkillResult(status=ResultStatus.SUCCESS, reply="\n".join(lines))
