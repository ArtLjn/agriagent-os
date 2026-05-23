from datetime import date
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.agents.tools import get_crop_cycle_info, get_recent_farm_logs, get_cycle_cost_summary, get_weather_forecast


class TestGetWeatherForecast:
    """测试天气工具。"""

    @patch("app.agents.tools.fetch_weather")
    @patch("app.agents.tools.check_weather_warnings")
    def test_returns_formatted_weather(self, mock_warnings: Mock, mock_fetch: Mock) -> None:
        """验证返回格式化天气字符串。"""
        mock_fetch.return_value = {
            "daily": {
                "time": ["2026-05-23"],
                "temperature_2m_max": [28.0],
                "temperature_2m_min": [18.0],
                "precipitation_sum": [0.0],
                "windspeed_10m_max": [10.0],
            }
        }
        mock_warnings.return_value = []

        result = get_weather_forecast.func("徐州")

        assert "徐州" in result
        assert "2026-05-23" in result
        mock_fetch.assert_called_once()


class TestGetCropCycleInfo:
    """测试茬口信息工具。"""

    @patch("app.agents.tools.SessionLocal")
    def test_returns_cycle_details(self, mock_session_local: Mock) -> None:
        """验证返回茬口详情字符串。"""
        mock_db = MagicMock()
        mock_cycle = MagicMock()
        mock_cycle.name = "西瓜春茬"
        mock_cycle.start_date = date(2026, 3, 1)
        mock_cycle.field_name = "一号地"
        mock_cycle.status = "active"
        mock_stage = MagicMock()
        mock_stage.name = "开花期"
        mock_stage.start_date = date(2026, 4, 15)
        mock_stage.end_date = date(2026, 5, 10)
        mock_stage.is_current = 1
        mock_cycle.stages = [mock_stage]
        mock_db.query.return_value.filter.return_value.first.return_value = mock_cycle
        mock_session_local.return_value = mock_db

        result = get_crop_cycle_info.func(1)

        assert "西瓜春茬" in result
        assert "开花期" in result
        mock_db.close.assert_called_once()

    @patch("app.agents.tools.SessionLocal")
    def test_cycle_not_found(self, mock_session_local: Mock) -> None:
        """茬口不存在时返回提示。"""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session_local.return_value = mock_db

        result = get_crop_cycle_info.func(999)

        assert "未找到" in result
        mock_db.close.assert_called_once()


class TestGetRecentFarmLogs:
    """测试农事记录工具。"""

    @patch("app.agents.tools.SessionLocal")
    def test_returns_logs_summary(self, mock_session_local: Mock) -> None:
        """验证返回最近农事记录。"""
        mock_db = MagicMock()
        mock_log = MagicMock()
        mock_log.operation_type = "浇水"
        mock_log.operation_date = date(2026, 5, 20)
        mock_log.note = "浇透水"
        mock_db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_log]
        mock_session_local.return_value = mock_db

        result = get_recent_farm_logs.func(1, days=7)

        assert "浇水" in result
        assert "浇透水" in result
        mock_db.close.assert_called_once()


class TestGetCycleCostSummary:
    """测试成本汇总工具。"""

    @patch("app.agents.tools.SessionLocal")
    def test_returns_cost_summary(self, mock_session_local: Mock) -> None:
        """验证返回成本收支汇总。"""
        mock_db = MagicMock()
        mock_cost = MagicMock()
        mock_cost.record_type = "cost"
        mock_cost.category = "肥料"
        mock_cost.amount = 500
        mock_income = MagicMock()
        mock_income.record_type = "income"
        mock_income.category = "销售"
        mock_income.amount = 3000
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_cost, mock_income]
        mock_session_local.return_value = mock_db

        result = get_cycle_cost_summary.func(1)

        assert "500" in result
        assert "3000" in result
        mock_db.close.assert_called_once()
