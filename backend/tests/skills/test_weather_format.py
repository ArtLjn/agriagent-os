"""天气预报格式化测试 — 验证 Markdown 表格输出。"""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from skillify.core.context import SkillContext

_weather_mod = importlib.import_module("app.agent.skills.weather.scripts.main")
WeatherSkill = _weather_mod.WeatherSkill


def _make_weather_data(days=3) -> dict:
    """构造模拟天气数据（3天）。"""
    return {
        "daily": {
            "time": ["2026-05-28", "2026-05-29", "2026-05-30"],
            "temperature_2m_max": [28, 22, 25],
            "temperature_2m_min": [18, 16, 17],
            "precipitation_sum": [0, 8, 2.5],
            "windspeed_10m_max": [5, 12, 8],
        }
    }


class TestWeatherFormatMarkdown:
    """验证天气回复使用结构化文本格式。"""

    def test_reply_starts_with_location_emoji(self):
        """回复以城市信息开头。"""
        data = _make_weather_data()
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert reply.startswith("城市: 苏州")

    def test_reply_contains_markdown_table(self):
        """回复包含未来天数和逐日天气。"""
        data = _make_weather_data()
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert "未来天数: 3天" in reply
        assert "5/28: 天气" in reply

    def test_reply_contains_weather_emoji(self):
        """天气列包含 emoji 图标。"""
        data = _make_weather_data()
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert "☀️" in reply
        assert "🌧️" in reply

    def test_date_format_m_d(self):
        """日期格式为 M/D（如 5/28）。"""
        data = _make_weather_data()
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert "5/28" in reply
        assert "5/29" in reply

    def test_only_three_days_shown(self):
        """只展示 3 天数据。"""
        data = _make_weather_data()
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert "5/31" not in reply

    def test_warning_appended_after_table(self):
        """预警信息在表格之后。"""
        data = _make_weather_data()
        data["daily"]["temperature_2m_max"][0] = 38  # 触发高温预警
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert "天气预警:" in reply
        warning_pos = reply.index("天气预警:")
        assert warning_pos > reply.index("5/30")

    def test_no_warning_shows_no_alert(self):
        """无预警时不出现 ⚠️。"""
        data = _make_weather_data()
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert "⚠️" not in reply

    def test_no_data_returns_fallback(self):
        """无数据时返回友好提示。"""
        reply = _weather_mod._format_weather_reply("苏州", {"daily": {}})
        assert "暂时获取不到天气数据" in reply


class TestWeatherLocationMissing:
    """验证缺少位置时走安全澄清路径。"""

    @pytest.mark.asyncio
    @patch.object(_weather_mod, "fetch_weather", new_callable=AsyncMock)
    @patch.object(_weather_mod, "SessionLocal")
    async def test_no_city_and_no_user_location_needs_clarify(
        self, mock_session_local, mock_fetch_weather
    ):
        """无 city、无用户设置、无 Farm.location 时不使用默认城市。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        mock_session_local.return_value = db

        result = await WeatherSkill().execute({}, SkillContext(farm_id=1))

        assert result.status.value == "need_clarify"
        assert "城市" in result.reply
        mock_fetch_weather.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(_weather_mod, "fetch_weather", new_callable=AsyncMock)
    async def test_explicit_city_can_query_without_farm_location(
        self, mock_fetch_weather
    ):
        """用户显式给城市时不依赖 Farm.location。"""
        mock_fetch_weather.return_value = _make_weather_data()

        result = await WeatherSkill().execute({"city": "上海"}, SkillContext())

        assert result.status.value == "success"
        mock_fetch_weather.assert_awaited_once()
