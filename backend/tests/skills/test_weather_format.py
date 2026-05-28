"""天气预报格式化测试 — 验证 Markdown 表格输出。"""

import importlib

_weather_mod = importlib.import_module(
    "app.agent.skills.weather.scripts.main"
)
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
    """验证天气回复使用 Markdown 表格格式。"""

    def test_reply_starts_with_location_emoji(self):
        """回复以 📍 emoji + 地点开头。"""
        data = _make_weather_data()
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert reply.startswith("📍")

    def test_reply_contains_markdown_table(self):
        """回复包含 Markdown 表格（| 分隔符）。"""
        data = _make_weather_data()
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert "|" in reply
        assert "---" in reply

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
        assert "⚠️" in reply
        table_end = reply.rindex("|")
        warning_pos = reply.index("⚠️")
        assert warning_pos > table_end

    def test_no_warning_shows_no_alert(self):
        """无预警时不出现 ⚠️。"""
        data = _make_weather_data()
        reply = _weather_mod._format_weather_reply("苏州", data)
        assert "⚠️" not in reply

    def test_no_data_returns_fallback(self):
        """无数据时返回友好提示。"""
        reply = _weather_mod._format_weather_reply("苏州", {"daily": {}})
        assert "🌤️" in reply
