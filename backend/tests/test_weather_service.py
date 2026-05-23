from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.weather_service import check_weather_warnings, fetch_weather


class TestFetchWeather:
    """测试天气查询功能。"""

    @patch("app.services.weather_service.httpx.get")
    def test_fetch_weather_returns_dict_with_required_keys(self, mock_get: Mock) -> None:
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
        call_args = mock_get.call_args
        assert call_args.kwargs["params"]["latitude"] == 34.26
        assert call_args.kwargs["params"]["longitude"] == 117.18
        assert call_args.kwargs["timeout"] == 10

    @patch("app.services.weather_service.httpx.get")
    def test_fetch_weather_raises_on_http_error(self, mock_get: Mock) -> None:
        """验证 HTTP 错误时抛出 RuntimeError。"""
        mock_get.side_effect = httpx.HTTPError("连接超时")

        with pytest.raises(RuntimeError, match="天气 API 请求失败"):
            fetch_weather(lat=34.26, lon=117.18)


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
