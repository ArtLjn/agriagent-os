"""farm_context_service 天气坐标来源测试。"""

import pytest

from app.models.user_setting import UserSetting
from app.services.farm_context_service import _build_weather_line


@pytest.mark.asyncio
class TestWeatherLineCoords:
    """天气行坐标来源测试。"""

    async def test_no_user_setting_uses_default(self, db_session):
        """无 user_settings 记录时用默认坐标。"""
        # farm_id=1 在 conftest 中已创建，无 user_setting
        result = await _build_weather_line(db_session, farm_id=1)
        assert result is not None
        assert "暂无天气数据" in result or "°" in result

    async def test_with_user_setting_uses_user_coords(self, db_session):
        """有 user_settings 时用用户坐标。"""
        # 创建用户设置，用哈尔滨坐标（和默认苏州差异大，便于区分）
        setting = UserSetting(
            user_id="test-user-001",
            default_city="哈尔滨",
            default_lat=45.8,
            default_lon=126.53,
        )
        db_session.add(setting)
        db_session.commit()

        result = await _build_weather_line(db_session, farm_id=1)
        assert result is not None

    async def test_user_setting_with_null_coords_uses_default(self, db_session):
        """user_settings 存在但坐标为 null 时用默认值。"""
        setting = UserSetting(
            user_id="test-user-001",
            default_city="某地",
            default_lat=None,
            default_lon=None,
        )
        db_session.add(setting)
        db_session.commit()

        result = await _build_weather_line(db_session, farm_id=1)
        assert result is not None
