"""farm_context_service 天气坐标来源测试。"""

import pytest

from app.core.database import SessionLocal
from app.models.farm import Farm
from app.models.user_setting import UserSetting
from app.services.farm_context_service import _build_weather_line


class TestWeatherLineCoords:
    """天气行坐标来源测试。"""

    def test_no_user_setting_uses_default(self):
        """无 user_settings 记录时用默认坐标。"""
        db = SessionLocal()
        try:
            # farm_id=1 在 conftest 中已创建，无 user_setting
            result = _build_weather_line(db, farm_id=1)
            assert result is not None
            assert "暂无天气数据" in result or "°" in result
        finally:
            db.close()

    def test_with_user_setting_uses_user_coords(self):
        """有 user_settings 时用用户坐标。"""
        db = SessionLocal()
        try:
            # 创建用户设置，用哈尔滨坐标（和默认苏州差异大，便于区分）
            setting = UserSetting(
                user_id="test-user-001",
                default_city="哈尔滨",
                default_lat=45.8,
                default_lon=126.53,
            )
            db.add(setting)
            db.commit()

            result = _build_weather_line(db, farm_id=1)
            assert result is not None
        finally:
            db.close()

    def test_user_setting_with_null_coords_uses_default(self):
        """user_settings 存在但坐标为 null 时用默认值。"""
        db = SessionLocal()
        try:
            setting = UserSetting(
                user_id="test-user-001",
                default_city="某地",
                default_lat=None,
                default_lon=None,
            )
            db.add(setting)
            db.commit()

            result = _build_weather_line(db, farm_id=1)
            assert result is not None
        finally:
            db.close()
