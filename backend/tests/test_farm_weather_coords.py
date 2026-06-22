"""farm_context_service 天气坐标来源测试。"""

from unittest.mock import AsyncMock

import pytest

from app.models.farm import Farm
from app.models.user_setting import UserSetting
from app.services.farm_context_service import _build_weather_line


@pytest.mark.asyncio
class TestWeatherLineCoords:
    """天气行坐标来源测试。"""

    async def test_no_user_setting_uses_default(self, db_session, monkeypatch):
        """无 user_settings 记录时用默认坐标。"""
        fetch_weather = AsyncMock(return_value={"daily": {}})
        monkeypatch.setattr(
            "app.services.farm_context_service.weather_service.fetch_weather",
            fetch_weather,
        )

        # farm_id=1 在 conftest 中已创建，无 user_setting
        result = await _build_weather_line(db_session, farm_id=1)

        assert result is not None
        fetch_weather.assert_awaited_once_with(
            "",
            days=3,
            lat=34.26,
            lon=117.18,
        )

    async def test_farm_location_has_priority_over_user_setting(
        self, db_session, monkeypatch
    ):
        """农场经营地区存在时优先使用 farm.location，并补齐坐标。"""
        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        farm.location = "睢宁县"
        setting = UserSetting(
            user_id="test-user-001",
            default_city="徐州",
            default_lat=34.26,
            default_lon=117.18,
        )
        db_session.add(setting)
        db_session.commit()
        fetch_weather = AsyncMock(return_value={"daily": {}})
        monkeypatch.setattr(
            "app.services.farm_context_service.weather_service.fetch_weather",
            fetch_weather,
        )

        await _build_weather_line(db_session, farm_id=1)

        fetch_weather.assert_awaited_once_with(
            "睢宁县",
            days=3,
            lat=33.914129,
            lon=117.935535,
        )

    async def test_with_user_setting_uses_user_coords(self, db_session, monkeypatch):
        """Farm.location 缺失时用用户设置坐标兜底。"""
        # 创建用户设置，用哈尔滨坐标（和默认苏州差异大，便于区分）
        setting = UserSetting(
            user_id="test-user-001",
            default_city="哈尔滨",
            default_lat=45.8,
            default_lon=126.53,
        )
        db_session.add(setting)
        db_session.commit()
        fetch_weather = AsyncMock(return_value={"daily": {}})
        monkeypatch.setattr(
            "app.services.farm_context_service.weather_service.fetch_weather",
            fetch_weather,
        )

        await _build_weather_line(db_session, farm_id=1)

        fetch_weather.assert_awaited_once_with(
            "哈尔滨",
            days=3,
            lat=45.8,
            lon=126.53,
        )

    async def test_user_setting_with_null_coords_uses_city(self, db_session, monkeypatch):
        """user_settings 存在但坐标为 null 时用城市名兜底。"""
        setting = UserSetting(
            user_id="test-user-001",
            default_city="某地",
            default_lat=None,
            default_lon=None,
        )
        db_session.add(setting)
        db_session.commit()
        fetch_weather = AsyncMock(return_value={"daily": {}})
        monkeypatch.setattr(
            "app.services.farm_context_service.weather_service.fetch_weather",
            fetch_weather,
        )

        await _build_weather_line(db_session, farm_id=1)

        fetch_weather.assert_awaited_once_with("某地", days=3, lat=None, lon=None)
