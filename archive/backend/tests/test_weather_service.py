from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.domains.weather.service import check_weather_warnings, fetch_weather
from app.domains.weather.providers.base import DailyForecast, ProviderError, WeatherData


class TestFetchWeather:
    """测试天气查询功能。"""

    @pytest.mark.asyncio
    @patch("app.domains.weather.service.get_weather_strategy")
    async def test_fetch_weather_returns_dict_with_required_keys(
        self, mock_get_strategy: Mock
    ) -> None:
        """验证 fetch_weather 返回包含必需字段的字典。"""
        strategy = Mock()
        strategy.fetch = AsyncMock(
            return_value=WeatherData(
                location="34.26,117.18",
                provider="test",
                daily=[
                    DailyForecast("2026-05-23", 28.0, 18.0, "晴", 0.0, 10.0),
                    DailyForecast("2026-05-24", 30.0, 20.0, "雨", 5.0, 15.0),
                ],
                alerts=[],
                air_quality=None,
                current_temp=26.0,
            )
        )
        mock_get_strategy.return_value = strategy

        result = await fetch_weather(lat=34.26, lon=117.18)

        assert "daily" in result
        assert "location" in result
        strategy.fetch.assert_awaited_once_with("", 7, 34.26, 117.18)

    @pytest.mark.asyncio
    @patch("app.domains.weather.service.get_weather_strategy")
    async def test_fetch_weather_raises_on_http_error(
        self, mock_get_strategy: Mock
    ) -> None:
        """验证 HTTP 错误时抛出 RuntimeError。"""
        strategy = Mock()
        strategy.fetch = AsyncMock(side_effect=ProviderError("连接超时"))
        mock_get_strategy.return_value = strategy

        with pytest.raises(RuntimeError, match="天气数据获取失败"):
            await fetch_weather(lat=34.26, lon=117.18)


class TestCheckWeatherWarnings:
    """测试天气预警检测。"""

    def test_high_temperature_warning(self) -> None:
        """高温预警：最高温超过 35 度。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [36.0],
                "temperature_2m_min": [20.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [10.0],
            }
        }

        warnings = check_weather_warnings(data)

        assert any("高温" in w for w in warnings)

    def test_frost_warning(self) -> None:
        """霜冻预警：最低温低于 0 度。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [10.0],
                "temperature_2m_min": [-2.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [10.0],
            }
        }

        warnings = check_weather_warnings(data)

        assert any("霜冻" in w for w in warnings)

    def test_heavy_rain_warning(self) -> None:
        """大雨预警：日降水量超过 50 毫米。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [25.0],
                "temperature_2m_min": [18.0],
                "precipitation_sum": [60.0],
                "windspeed_10m_max": [10.0],
            }
        }

        warnings = check_weather_warnings(data)

        assert any("大雨" in w for w in warnings)

    def test_strong_wind_warning(self) -> None:
        """大风预警：最大风速超过 17 m/s（7 级）。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [25.0],
                "temperature_2m_min": [18.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [20.0],
            }
        }

        warnings = check_weather_warnings(data)

        assert any("大风" in w for w in warnings)

    def test_no_warning(self) -> None:
        """正常天气无预警。"""
        data = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [25.0],
                "temperature_2m_min": [18.0],
                "precipitation_sum": [5.0],
                "windspeed_10m_max": [10.0],
            }
        }

        warnings = check_weather_warnings(data)

        assert warnings == []

    def test_empty_daily_returns_empty(self) -> None:
        """空 daily 数据返回空预警列表。"""
        data = {"daily": {}}

        warnings = check_weather_warnings(data)

        assert warnings == []

    def test_mismatched_list_lengths(self) -> None:
        """列表长度不一致时不越界。"""
        data = {
            "daily": {
                "time": ["2026-05-23", "2026-05-24"],
                "temperature_2m_max": [36.0],
                "temperature_2m_min": [],
                "precipitation_sum": [60.0, 5.0],
                "windspeed_10m_max": [20.0, 10.0],
            }
        }

        warnings = check_weather_warnings(data)

        assert any("高温" in w for w in warnings)
        assert not any("霜冻" in w for w in warnings)
