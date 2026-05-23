from unittest.mock import Mock, patch

import pytest

from app.services.weather_service import check_weather_warnings, fetch_weather


class TestFetchWeather:
    """测试天气查询功能。"""

    @patch("app.services.weather_service.httpx.get")
    def test_fetch_weather_returns_dict_with_required_keys(self, mock_get):
        """验证 fetch_weather 返回包含必需字段的字典。"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "daily": {
                "time": ["2026-05-23", "2026-05-24"],
                "temperature_2m_max": [28.0, 30.0],
                "temperature_2m_min": [18.0, 20.0],
                "precipitation_sum": [0.0, 5.0],
                "windspeed_10m_max": [10.0, 15.0],
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = fetch_weather(lat=34.26, lon=117.18)

        assert "daily" in result
        assert "location" in result
        mock_get.assert_called_once()


class TestCheckWeatherWarnings:
    """测试天气预警检测。"""

    def test_high_temperature_warning(self):
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

    def test_frost_warning(self):
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

    def test_heavy_rain_warning(self):
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

    def test_strong_wind_warning(self):
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

    def test_no_warning(self):
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
