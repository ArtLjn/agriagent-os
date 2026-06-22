"""天气预报格式化测试 — 验证 Markdown 表格输出。"""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from skillify.core.context import SkillContext

from app.models.farm import Farm
from app.infra.skill_cache import clear_cache
from app.models.user import User
from app.models.user_setting import UserSetting

_weather_mod = importlib.import_module("app.agent.skills.weather.scripts.main")
WeatherSkill = _weather_mod.WeatherSkill


@pytest.fixture(autouse=True)
def _clear_weather_skill_cache():
    clear_cache("get_weather_forecast")
    yield
    clear_cache("get_weather_forecast")


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


class _SessionProxy:
    """给 WeatherSkill 测试复用 pytest 会话，忽略内部 close。"""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, name):
        return getattr(self._db, name)

    def close(self) -> None:
        pass


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
    async def test_no_city_and_no_user_location_uses_system_default(
        self, mock_session_local, mock_fetch_weather
    ):
        """无 city、无用户设置、无 Farm.location 时使用系统默认坐标兜底。"""
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        mock_session_local.return_value = db
        mock_fetch_weather.return_value = _make_weather_data()

        result = await WeatherSkill().execute({}, SkillContext(farm_id=1))

        assert result.status.value == "success"
        mock_fetch_weather.assert_awaited_once_with(
            "",
            days=3,
            lat=34.26,
            lon=117.18,
        )

    @pytest.mark.asyncio
    @patch.object(_weather_mod, "fetch_weather", new_callable=AsyncMock)
    async def test_explicit_city_can_query_without_farm_location(
        self, mock_fetch_weather, db_session, monkeypatch
    ):
        """用户显式给城市时不依赖 Farm.location，并补齐内置坐标。"""
        farm = db_session.query(Farm).filter(Farm.id == 1).first()
        farm.location = "睢宁县"
        db_session.commit()
        monkeypatch.setattr(
            _weather_mod,
            "SessionLocal",
            lambda: _SessionProxy(db_session),
        )
        mock_fetch_weather.return_value = _make_weather_data()

        result = await WeatherSkill().execute({"city": "苏州"}, SkillContext())

        assert result.status.value == "success"
        mock_fetch_weather.assert_awaited_once_with(
            "苏州",
            days=3,
            lat=31.299487,
            lon=120.581823,
        )
        db_session.refresh(farm)
        assert farm.location == "睢宁县"

    @pytest.mark.asyncio
    @patch.object(_weather_mod, "fetch_weather", new_callable=AsyncMock)
    async def test_explicit_location_parameter_is_supported(
        self, mock_fetch_weather
    ):
        """兼容 skill.md 声明的 location 参数，避免 LLM 传参被忽略。"""
        mock_fetch_weather.return_value = _make_weather_data()

        result = await WeatherSkill().execute(
            {"location": "苏州"},
            SkillContext(farm_id=1),
        )

        assert result.status.value == "success"
        mock_fetch_weather.assert_awaited_once_with(
            "苏州",
            days=3,
            lat=31.299487,
            lon=120.581823,
        )

    @pytest.mark.asyncio
    @patch.object(_weather_mod, "fetch_weather", new_callable=AsyncMock)
    async def test_ambiguous_location_requires_clarification(
        self, mock_fetch_weather
    ):
        """裸鼓楼区可能属于南京或徐州，不能静默查询。"""
        result = await WeatherSkill().execute(
            {"location": "鼓楼区"},
            SkillContext(farm_id=1),
        )

        assert result.status.value == "need_clarify"
        assert "南京鼓楼区" in result.reply
        assert "徐州鼓楼区" in result.reply
        mock_fetch_weather.assert_not_awaited()

    @pytest.mark.asyncio
    @patch.object(_weather_mod, "fetch_weather", new_callable=AsyncMock)
    async def test_ambiguous_location_uses_saved_coordinates(
        self, mock_fetch_weather, db_session, monkeypatch
    ):
        """用户已保存同名地点坐标时，Agent 直接按经纬度查询。"""
        setting = UserSetting(
            user_id="test-user-001",
            default_city="鼓楼区",
            default_lat=34.28889,
            default_lon=117.18559,
        )
        db_session.add(setting)
        db_session.commit()
        monkeypatch.setattr(
            _weather_mod,
            "SessionLocal",
            lambda: _SessionProxy(db_session),
        )
        mock_fetch_weather.return_value = _make_weather_data()

        result = await WeatherSkill().execute(
            {"location": "鼓楼区"},
            SkillContext(farm_id=1),
        )

        assert result.status.value == "success"
        mock_fetch_weather.assert_awaited_once_with(
            "鼓楼区",
            days=3,
            lat=34.28889,
            lon=117.18559,
        )

    @pytest.mark.asyncio
    @patch.object(_weather_mod, "fetch_weather", new_callable=AsyncMock)
    async def test_qualified_ambiguous_location_uses_alias_coords(
        self, mock_fetch_weather
    ):
        """带上级城市的重名区县可安全解析坐标。"""
        mock_fetch_weather.return_value = _make_weather_data()

        result = await WeatherSkill().execute(
            {"location": "徐州鼓楼区"},
            SkillContext(farm_id=1),
        )

        assert result.status.value == "success"
        mock_fetch_weather.assert_awaited_once_with(
            "徐州鼓楼区",
            days=3,
            lat=34.28889,
            lon=117.18559,
        )

    @pytest.mark.asyncio
    @patch.object(_weather_mod, "fetch_weather", new_callable=AsyncMock)
    async def test_unspecified_city_uses_farm_location_first(
        self, mock_fetch_weather, db_session, monkeypatch
    ):
        """未指定城市时优先使用当前农场经营地区。"""
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
        monkeypatch.setattr(
            _weather_mod,
            "SessionLocal",
            lambda: _SessionProxy(db_session),
        )
        mock_fetch_weather.return_value = _make_weather_data()

        result = await WeatherSkill().execute({}, SkillContext(farm_id=1))

        assert result.status.value == "success"
        mock_fetch_weather.assert_awaited_once_with(
            "睢宁县",
            days=3,
            lat=33.914129,
            lon=117.935535,
        )

    @pytest.mark.asyncio
    @patch.object(_weather_mod, "fetch_weather", new_callable=AsyncMock)
    async def test_unspecified_city_falls_back_to_user_setting_coordinates(
        self, mock_fetch_weather, db_session, monkeypatch
    ):
        """农场经营地区缺失时使用旧用户设置坐标兜底。"""
        user = User(
            id="weather-skill-user",
            phone="19000000002",
            password_hash="hash",
            nickname="天气用户",
        )
        farm = Farm(id=80, name="技能农场", user_id=user.id, location=None)
        setting = UserSetting(
            user_id=user.id,
            default_city="徐州",
            default_lat=34.26,
            default_lon=117.18,
        )
        db_session.add_all([user, farm, setting])
        db_session.commit()
        monkeypatch.setattr(
            _weather_mod,
            "SessionLocal",
            lambda: _SessionProxy(db_session),
        )
        mock_fetch_weather.return_value = _make_weather_data()

        result = await WeatherSkill().execute({}, SkillContext(farm_id=80))

        assert result.status.value == "success"
        mock_fetch_weather.assert_awaited_once_with(
            "徐州",
            days=3,
            lat=34.26,
            lon=117.18,
        )
