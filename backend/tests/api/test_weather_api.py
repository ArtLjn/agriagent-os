from unittest.mock import AsyncMock, patch


def test_forecast_uses_default_coordinates_when_location_is_placeholder(client):
    """无有效位置参数时，天气接口使用配置默认坐标兜底。"""
    weather_data = {
        "location": "默认地块",
        "daily": {
            "time": ["2026-06-09"],
            "temperature_2m_max": [32.1],
            "temperature_2m_min": [17.2],
            "precipitation_sum": [0.0],
            "windspeed_10m_max": [11.2],
        },
        "warnings": [],
    }

    with patch(
        "app.api.weather.fetch_weather",
        new_callable=AsyncMock,
        return_value=weather_data,
    ) as mock_fetch:
        response = client.get("/weather/forecast")

    assert response.status_code == 200
    mock_fetch.assert_awaited_once_with("当前地块", 7, 34.26, 117.18)
