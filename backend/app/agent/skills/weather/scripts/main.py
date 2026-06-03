"""天气预报 Skill。"""

from skillify.models.schemas import ResultStatus, SkillResult
from skillify.skills.base import Skill

from app.core.config import settings
from app.core.database import SessionLocal
from app.infra.skill_cache import cached
from app.services.weather_service import check_weather_warnings, fetch_weather

# 常见城市名列表（用于从消息中提取）
_CITIES = {
    "北京",
    "上海",
    "天津",
    "重庆",
    "哈尔滨",
    "长春",
    "沈阳",
    "大连",
    "石家庄",
    "太原",
    "呼和浩特",
    "济南",
    "青岛",
    "郑州",
    "西安",
    "兰州",
    "银川",
    "西宁",
    "乌鲁木齐",
    "合肥",
    "南京",
    "苏州",
    "无锡",
    "杭州",
    "宁波",
    "福州",
    "厦门",
    "宁德",
    "南昌",
    "济南",
    "武汉",
    "长沙",
    "广州",
    "深圳",
    "南宁",
    "海口",
    "成都",
    "贵阳",
    "昆明",
    "拉萨",
    "杭州",
    "金华",
    "温州",
    "嘉兴",
    "台州",
    "绍兴",
}


def _extract_city(text: str) -> str | None:
    """从文本中提取城市名。"""
    for city in _CITIES:
        if city in text:
            return city
    return None


def _get_user_location(farm_id: int) -> tuple[str, float, float]:
    """从 user_settings 读取用户位置（城市名、坐标），无记录时降级到默认值。"""
    default_city = "苏州"
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
                    city = setting.default_city or default_city
                    return city, setting.default_lat, setting.default_lon
        finally:
            db.close()
    except Exception:
        pass
    return default_city, default_lat, default_lon


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
    """将天气数据格式化为结构化文本，由 LLM 决定最终呈现方式。"""
    daily = data.get("daily", {})
    times = daily.get("time", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    feels_like_max = daily.get("apparent_temperature_max", [])
    feels_like_min = daily.get("apparent_temperature_min", [])
    precips = daily.get("precipitation_sum", [])
    precip_hours = daily.get("precipitation_hours", [])
    winds = daily.get("windspeed_10m_max", [])
    uv_index = daily.get("uv_index_max", [])
    humidity = daily.get("relative_humidity_2m_mean", [])

    if not times:
        return "暂时获取不到天气数据，请稍后再试。"

    current = data.get("current_weather", {})
    current_temp = current.get("temperature", None)
    count = min(3, len(times))

    lines = [f"城市: {location}", f"未来天数: {count}天"]
    if current_temp is not None:
        lines.append(f"当前温度: {current_temp}℃")
    lines.append("")

    for i in range(count):
        day = _format_date_m_d(times[i])
        max_t = max_temps[i] if i < len(max_temps) else "-"
        min_t = min_temps[i] if i < len(min_temps) else "-"
        p = precips[i] if i < len(precips) else 0
        ph = precip_hours[i] if i < len(precip_hours) else 0
        w = winds[i] if i < len(winds) else "-"
        uv = uv_index[i] if i < len(uv_index) else "-"
        h = humidity[i] if i < len(humidity) else "-"
        emoji = _weather_emoji(float(p), float(max_t) if max_t != "-" else 20)

        if i < len(feels_like_max) and i < len(feels_like_min):
            feels = f"{feels_like_min[i]:.0f}~{feels_like_max[i]:.0f}"
        else:
            feels = "-"

        lines.append(
            f"{day}: 天气{emoji}, 最高{max_t}℃, 最低{min_t}℃, "
            f"体感{feels}℃, 降水{p}mm({ph}h), 风速{w}m/s, 湿度{h}%, UV{uv}"
        )

    hourly = data.get("hourly", {})
    hourly_time = hourly.get("time", [])
    hourly_precip = hourly.get("precipitation", [])
    hourly_prob = hourly.get("precipitation_probability", [])

    rain_times = []
    if hourly_time and hourly_precip:
        for t, rain, prob in zip(
            hourly_time[:24], hourly_precip[:24], hourly_prob[:24]
        ):
            if rain > 0 or prob >= 50:
                hour = int(t.split("T")[1].split(":")[0])
                rain_times.append(f"{hour}时({prob}%)")

    if rain_times:
        lines.append("")
        lines.append(f"今日降水时段: {', '.join(rain_times[:6])}")
        if len(rain_times) > 6:
            lines.append(f"还有 {len(rain_times) - 6} 个时段")

    warnings = check_weather_warnings(data)
    if warnings:
        lines.append("")
        lines.append("天气预警:")
        for w in warnings:
            lines.append(f"- {w}")

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
                "city": {
                    "type": "string",
                    "description": "要查询的城市名，如'北京'、'上海'、'宁德'等。",
                }
            },
            "required": [],
        }

    @cached(ttl_seconds=1800)
    async def execute(self, params: dict, context) -> SkillResult:
        farm_id = getattr(context, "farm_id", 1) or 1

        # 优先使用参数中的城市名
        city = params.get("city", "").strip()
        if city:
            location, lat, lon = city, None, None
        else:
            # 降级到用户设置的位置
            location, lat, lon = _get_user_location(farm_id)

        data = await fetch_weather(location, days=3, lat=lat, lon=lon)
        reply = _format_weather_reply(location, data)
        return SkillResult(status=ResultStatus.SUCCESS, reply=reply)
