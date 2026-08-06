from unittest.mock import AsyncMock, patch

from app.domains.farm.models import Farm
from app.domains.users.settings_models import UserSetting


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
        "app.domains.weather.routes.fetch_weather",
        new_callable=AsyncMock,
        return_value=weather_data,
    ) as mock_fetch:
        response = client.get("/weather/forecast")

    assert response.status_code == 200
    mock_fetch.assert_awaited_once_with("当前地块", 7, 34.26, 117.18)


def test_authenticated_forecast_uses_farm_location(
    client, auth_headers, db_session
):
    """认证用户默认天气跟随当前默认农场经营地区，并透传可信坐标。"""
    farm = db_session.query(Farm).filter(Farm.id == 1).first()
    farm.location = "睢宁县"
    db_session.add(
        UserSetting(
            user_id="test-user-001",
            default_city="徐州",
            default_lat=34.26,
            default_lon=117.18,
        )
    )
    db_session.commit()
    weather_data = {
        "location": "睢宁县",
        "daily": {},
        "warnings": [],
    }

    with patch(
        "app.domains.weather.routes.fetch_weather",
        new_callable=AsyncMock,
        return_value=weather_data,
    ) as mock_fetch:
        response = client.get("/weather/forecast", headers=auth_headers)

    assert response.status_code == 200
    mock_fetch.assert_awaited_once_with("睢宁县", 7, 33.914129, 117.935535)


def test_authenticated_forecast_fills_coordinates_from_farm_location(
    client, auth_headers, db_session
):
    """农场只有文本地区时，用共享区县坐标补齐，避免 Provider 地名解析漂移。"""
    farm = db_session.query(Farm).filter(Farm.id == 1).first()
    farm.location = "虎丘区"
    db_session.commit()
    weather_data = {
        "location": "虎丘区",
        "daily": {},
        "warnings": [],
    }

    with patch(
        "app.domains.weather.routes.fetch_weather",
        new_callable=AsyncMock,
        return_value=weather_data,
    ) as mock_fetch:
        response = client.get("/weather/forecast", headers=auth_headers)

    assert response.status_code == 200
    mock_fetch.assert_awaited_once_with("虎丘区", 7, 31.3296, 120.4342)


def test_authenticated_forecast_rejects_ambiguous_district(
    client, auth_headers, db_session
):
    """重名区县无坐标时返回明确错误，避免查询到错误城市天气。"""
    farm = db_session.query(Farm).filter(Farm.id == 1).first()
    farm.location = "鼓楼区"
    db_session.commit()

    with patch("app.domains.weather.routes.fetch_weather", new_callable=AsyncMock) as mock_fetch:
        response = client.get("/weather/forecast", headers=auth_headers)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "WEATHER_LOCATION_AMBIGUOUS"
    mock_fetch.assert_not_awaited()


def test_authenticated_forecast_uses_saved_coords_for_ambiguous_location(
    client, auth_headers, db_session
):
    """用户设置保存了重名区县坐标时，直接按经纬度查询。"""
    db_session.add(
        UserSetting(
            user_id="test-user-001",
            default_city="鼓楼区",
            default_lat=34.28889,
            default_lon=117.18559,
        )
    )
    db_session.commit()
    weather_data = {
        "location": "鼓楼区",
        "daily": {},
        "warnings": [],
    }

    with patch(
        "app.domains.weather.routes.fetch_weather",
        new_callable=AsyncMock,
        return_value=weather_data,
    ) as mock_fetch:
        response = client.get(
            "/weather/forecast?location=%E9%BC%93%E6%A5%BC%E5%8C%BA",
            headers=auth_headers,
        )

    assert response.status_code == 200
    mock_fetch.assert_awaited_once_with("鼓楼区", 7, 34.28889, 117.18559)


def test_authenticated_forecast_explicit_location_does_not_update_farm(
    client, auth_headers, db_session
):
    """显式 location 只覆盖本次天气查询，不修改 farm.location。"""
    farm = db_session.query(Farm).filter(Farm.id == 1).first()
    farm.location = "睢宁县"
    db_session.commit()
    weather_data = {
        "location": "上海",
        "daily": {},
        "warnings": [],
    }

    with patch(
        "app.domains.weather.routes.fetch_weather",
        new_callable=AsyncMock,
        return_value=weather_data,
    ) as mock_fetch:
        response = client.get(
            "/weather/forecast?location=上海",
            headers=auth_headers,
        )

    db_session.refresh(farm)
    assert response.status_code == 200
    mock_fetch.assert_awaited_once_with("上海", 7, None, None)
    assert farm.location == "睢宁县"
