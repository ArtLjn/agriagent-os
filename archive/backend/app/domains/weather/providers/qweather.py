"""和风天气 Provider 实现（支持 API Key 和 appid/appsecret 签名认证）。"""

import base64
import hashlib
import hmac
import logging

import httpx

from app.domains.weather.providers.base import (
    AirQuality,
    DailyForecast,
    ProviderError,
    WeatherData,
    WeatherProvider,
)

logger = logging.getLogger(__name__)

_QWEATHER_BASE = "https://p32k5pxvta.re.qweatherapi.com/v7"
_QWEATHER_GEO = "https://p32k5pxvta.re.qweatherapi.com/v2/city/lookup"


class QWeatherProvider(WeatherProvider):
    """和风天气 Provider（中国数据源）。

    支持两种认证方式：
    1. API Key 模式（免费/标准版）：传入 api_key
    2. 签名认证模式（商业版）：传入 appid + appsecret
    """

    def __init__(self, api_key: str = "", appid: str = "", appsecret: str = "") -> None:
        self._api_key = api_key
        self._appid = appid
        self._appsecret = appsecret
        self._use_sign = bool(appid and appsecret)

    def _build_params(self, **kwargs) -> dict:
        """构建请求参数（含认证信息）。"""
        params = dict(kwargs)
        if self._use_sign:
            params["appid"] = self._appid
            params["sign"] = self._sign(params)
        else:
            params["key"] = self._api_key
        return params

    def _sign(self, params: dict) -> str:
        """和风天气签名认证。

        规则：
        1. 将参数（不含 sign）按参数名升序排列
        2. 按 key1=value1&key2=value2 格式拼接
        3. HMAC-SHA256(appsecret, 拼接字符串)
        4. Base64 编码
        """
        sorted_items = sorted(params.items())
        query = "&".join(f"{k}={v}" for k, v in sorted_items)
        signature = hmac.new(
            self._appsecret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    async def _lookup_city(self, location: str) -> tuple[str, float, float]:
        """城市名 → 城市 ID + 经纬度。

        Geo API 可能不可用，失败时返回空 ID + 默认经纬度（徐州）。
        天气 API 支持直接使用经纬度查询。
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    _QWEATHER_GEO,
                    params=self._build_params(location=location, number=1),
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("code") == "200":
                locations = data.get("location", [])
                if locations:
                    loc = locations[0]
                    return loc["id"], float(loc["lat"]), float(loc["lon"])
        except (httpx.HTTPError, KeyError):
            logger.debug("和风天气 GeoAPI 不可用，使用默认经纬度")

        # 回退：使用默认经纬度（徐州）
        return "", 34.26, 117.18

    async def fetch_daily(
        self,
        location: str = "",
        days: int = 7,
        lat: float | None = None,
        lon: float | None = None,
    ) -> WeatherData:
        """获取天气预报。"""
        # 优先使用传入坐标，否则 lookup
        _placeholder_names = ("当前地块", "地块", "")
        if lat is None or lon is None:
            if location and location not in _placeholder_names:
                city_id, lat, lon = await self._lookup_city(location)
            else:
                raise ProviderError("未提供有效位置信息（需要城市名或 GPS 坐标）")
        else:
            city_id = ""

        # 优先使用经纬度（更可靠）
        location_param = f"{lon},{lat}" if lat and lon else city_id
        location = location or f"{lat:.2f},{lon:.2f}"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_QWEATHER_BASE}/weather/{days}d",
                    params=self._build_params(location=location_param),
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"和风天气请求失败: {exc}") from exc

        code = data.get("code", "")
        if code == "401":
            raise ProviderError("和风天气 API key 无效")
        if code == "429":
            raise ProviderError("和风天气 API 配额已用完")
        if code != "200":
            raise ProviderError(f"和风天气 API 错误: code={code}")

        daily_list = data.get("daily", [])
        forecasts: list[DailyForecast] = []
        for day in daily_list:
            forecasts.append(
                DailyForecast(
                    date=day.get("fxDate", ""),
                    temp_max=float(day.get("tempMax", 0)),
                    temp_min=float(day.get("tempMin", 0)),
                    weather_text=day.get("textDay", ""),
                    precipitation=float(day.get("precip", 0)),
                    wind_speed=float(day.get("windSpeedDay", 0)),
                )
            )

        current_temp = await self._fetch_current_temp(location_param)

        return WeatherData(
            location=location,
            provider="qweather",
            daily=forecasts,
            alerts=[],
            air_quality=None,
            current_temp=current_temp,
        )

    async def _fetch_current_temp(self, city_id: str) -> float | None:
        """获取当前温度。"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_QWEATHER_BASE}/weather/now",
                    params=self._build_params(location=city_id),
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") == "200":
                    now = data.get("now", {})
                    return float(now.get("temp", 0))
        except Exception:
            logger.warning("获取实时温度失败")
        return None

    async def fetch_air_quality(self, location: str) -> AirQuality | None:
        """获取空气质量。"""
        city_id, _lat, _lon = await self._lookup_city(location)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{_QWEATHER_BASE}/air/now",
                    params=self._build_params(location=city_id),
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError(f"和风天气 AQI 请求失败: {exc}") from exc

        if data.get("code") != "200":
            return None

        now = data.get("now", {})
        return AirQuality(
            aqi=int(now.get("aqi", 0)),
            category=now.get("category", ""),
            pm25=float(now.get("pm2p5", 0)),
        )

    async def can_serve(self, location: str) -> bool:
        """判断是否为和风天气覆盖的中国城市。

        由于 Geo API 不可用，这里简化处理：只要配置了 API key 就认为可用。
        """
        return bool(self._api_key or self._use_sign)
