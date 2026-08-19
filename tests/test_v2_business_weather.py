"""天气 Business 服务和 Agent Skill 的预警能力回归。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.skills.loader import load_all
from business.api import weather as weather_api
from business.services import weather_service


def _open_meteo_payload() -> dict:
    return {
        "current": {"temperature_2m": 29},
        "daily": {
            "time": ["2026-08-11", "2026-08-12", "2026-08-13", "2026-08-14"],
            "temperature_2m_max": [36, 28, 30, 31],
            "temperature_2m_min": [-1, 20, 21, 22],
            "precipitation_sum": [55, 0, 0, 0],
            "windspeed_10m_max": [18, 4, 5, 6],
            "weathercode": [95, 1, 2, 3],
        },
    }


def test_parse_official_alerts_filters_city_and_deduplicates() -> None:
    payload = {
        "code": 0,
        "data": [
            {
                "headline": "苏州市气象台发布暴雨黄色预警",
                "title": "",
                "description": "预计未来三小时有强降水。",
            },
            {
                "headline": "苏州市气象台发布暴雨黄色预警",
                "title": "",
                "description": "预计未来三小时有强降水。",
            },
            {
                "headline": "南京市气象台发布高温预警",
                "title": "",
                "description": "无关城市。",
            },
            {
                "headline": "江苏省气象台发布暴雨蓝色预警",
                "title": "江苏省发布暴雨蓝色预警",
                "description": "预计今天苏州地区将出现强降雨。",
            },
        ],
    }

    assert weather_service._parse_official_alerts(payload, "苏州") == [
        "苏州市气象台发布暴雨黄色预警: 预计未来三小时有强降水。",
        "江苏省气象台发布暴雨蓝色预警: 预计今天苏州地区将出现强降雨。",
    ]


def test_alert_terms_include_city_and_district_names() -> None:
    terms = weather_service._alert_terms_for("江苏省苏州市虎丘区")

    assert "苏州" in terms
    assert "虎丘区" in terms


def test_complete_summary_contains_threshold_warnings_and_frontend_days() -> None:
    summary = weather_service._summarize_open_meteo(
        _open_meteo_payload(), "苏州市", days=4
    )

    completed = weather_service._complete_summary(summary, ["苏州市官方预警"])

    assert len(completed["daily"]) == 4
    assert completed["warnings"] == [
        "苏州市官方预警",
        "2026-08-11 高温预警：最高温 36℃",
        "2026-08-11 霜冻预警：最低温 -1℃",
        "2026-08-11 大雨预警：降水量 55mm",
        "2026-08-11 大风预警：最大风速 18m/s",
    ]
    assert completed["days"][0] == {
        "date": "2026-08-11",
        "max_temp": 36,
        "min_temp": -1,
        "precipitation": 55,
        "weather_code": 95,
        "weather_text": "雷暴",
        "wind_speed": 18,
    }


def test_explicit_unknown_location_is_not_replaced_by_default_coords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        weather_api.farm_crud_service,
        "get_farm_by_id",
        lambda *_args, **_kwargs: SimpleNamespace(location="苏州市"),
    )
    monkeypatch.setattr(weather_api.location_service, "find_coords", lambda *_: None)

    assert weather_api._resolve_location(object(), 1, "不存在的城市", None, None) == (
        "不存在的城市",
        None,
        None,
    )


def test_user_default_location_is_preferred_when_location_is_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        weather_api.farm_crud_service,
        "get_farm_by_id",
        lambda *_args, **_kwargs: SimpleNamespace(location="北京"),
    )
    monkeypatch.setattr(
        weather_api.user_service,
        "get_user_settings",
        lambda user_id: {
            "user_id": user_id,
            "default_city": "江苏省苏州市",
            "default_lat": 31.299487,
            "default_lon": 120.581823,
        },
    )
    monkeypatch.setattr(
        weather_api.location_service,
        "find_coords",
        lambda *_args: (_ for _ in ()).throw(
            AssertionError("已有用户默认坐标时不应再次猜测坐标")
        ),
    )

    assert weather_api._resolve_location(object(), 1, None, None, None, "user-1") == (
        "江苏省苏州市",
        31.299487,
        120.581823,
    )


def test_explicit_location_overrides_user_default_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        weather_api.farm_crud_service,
        "get_farm_by_id",
        lambda *_args, **_kwargs: SimpleNamespace(location="北京"),
    )
    monkeypatch.setattr(
        weather_api.user_service,
        "get_user_settings",
        lambda *_args: {
            "default_city": "江苏省苏州市",
            "default_lat": 31.299487,
            "default_lon": 120.581823,
        },
    )
    monkeypatch.setattr(
        weather_api.location_service,
        "find_coords",
        lambda city: (39.9042, 116.4074) if city == "北京市" else None,
    )

    assert weather_api._resolve_location(
        object(), 1, "北京市", None, None, "user-1"
    ) == ("北京市", 39.9042, 116.4074)


@pytest.mark.asyncio
async def test_fetch_weather_merges_official_alerts_without_blocking_forecast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(weather_service, "_qweather_key", lambda: "")
    monkeypatch.setattr(
        weather_service,
        "_fetch_open_meteo",
        lambda *_args, **_kwargs: _async_result(_open_meteo_payload()),
    )
    monkeypatch.setattr(
        weather_service,
        "_fetch_official_alerts",
        lambda *_args, **_kwargs: _async_result(["苏州市官方预警"]),
    )

    result = await weather_service._fetch_weather_async(
        "苏州市", lat=31.3, lon=120.6, days=4
    )

    assert result["provider"] == "open-meteo"
    assert len(result["daily"]) == 4
    assert result["warnings"][0] == "苏州市官方预警"


async def _async_result(value):
    return value


@pytest.mark.asyncio
async def test_weather_skill_searches_unknown_location_and_retries() -> None:
    calls: list[tuple[str, dict]] = []

    class Business:
        async def call_mcp_tool(
            self, name: str, arguments: dict, *, risk_level: str
        ) -> dict:
            calls.append((name, arguments))
            if name == "get_weather" and arguments.get("location") == "火星":
                return {
                    "error": "unknown_location",
                    "hint": "call search_cities first",
                }
            if name == "search_cities":
                return {"cities": [{"full_name": "江苏省苏州市"}]}
            return {"location": "江苏省苏州市", "warnings": []}

    skill = next(skill for skill in load_all() if skill.name == "get_weather")
    business = Business()
    ctx = SimpleNamespace(
        turn=SimpleNamespace(user_input="火星天气怎么样", events=[]),
        business_client=business,
        call_mcp_tool=business.call_mcp_tool,
    )

    result = await skill.execute({"location": "火星", "days": 7}, ctx)

    assert result.ok
    assert calls == [
        ("get_weather", {"location": "火星", "days": 7}),
        ("search_cities", {"keyword": "火星"}),
        ("get_weather", {"location": "江苏省苏州市", "days": 7}),
    ]


@pytest.mark.asyncio
async def test_weather_skill_uses_user_default_location_when_omitted() -> None:
    calls: list[tuple[str, dict]] = []

    class Business:
        async def call_mcp_tool(
            self, name: str, arguments: dict, *, risk_level: str
        ) -> dict:
            calls.append((name, arguments))
            if name == "manage_user_settings":
                return {
                    "configured": True,
                    "settings": {
                        "default_city": "江苏省徐州市睢宁县",
                        "default_lat": 33.9141,
                        "default_lon": 117.936,
                    },
                }
            return {"location": arguments["location"], "warnings": []}

    skill = next(skill for skill in load_all() if skill.name == "get_weather")
    business = Business()
    ctx = SimpleNamespace(
        turn=SimpleNamespace(user_input="天气如何", events=[]),
        business_client=business,
        call_mcp_tool=business.call_mcp_tool,
    )

    result = await skill.execute({}, ctx)

    assert result.ok
    assert calls == [
        ("manage_user_settings", {"operation": "query"}),
        ("get_weather", {"location": "江苏省徐州市睢宁县"}),
    ]


@pytest.mark.asyncio
async def test_weather_skill_falls_back_when_user_default_is_unavailable() -> None:
    calls: list[tuple[str, dict]] = []

    class Business:
        async def call_mcp_tool(
            self, name: str, arguments: dict, *, risk_level: str
        ) -> dict:
            calls.append((name, arguments))
            if name == "manage_user_settings":
                return {"configured": False, "settings": {}}
            return {"location": "苏州", "warnings": []}

    skill = next(skill for skill in load_all() if skill.name == "get_weather")
    business = Business()
    ctx = SimpleNamespace(
        turn=SimpleNamespace(user_input="天气如何", events=[]),
        business_client=business,
        call_mcp_tool=business.call_mcp_tool,
    )

    result = await skill.execute({}, ctx)

    assert result.ok
    assert calls == [
        ("manage_user_settings", {"operation": "query"}),
        ("get_weather", {}),
    ]


@pytest.mark.asyncio
async def test_weather_skill_resolves_explicit_city_when_model_omits_location() -> None:
    calls: list[tuple[str, dict]] = []

    class Business:
        async def call_mcp_tool(
            self, name: str, arguments: dict, *, risk_level: str
        ) -> dict:
            calls.append((name, arguments))
            if name == "search_cities":
                return {"cities": [{"full_name": "北京市东城区"}]}
            if name == "manage_user_settings":
                raise AssertionError("明确城市不应读取默认位置")
            return {"location": arguments["location"], "warnings": []}

    skill = next(skill for skill in load_all() if skill.name == "get_weather")
    business = Business()
    ctx = SimpleNamespace(
        turn=SimpleNamespace(user_input="查询北京市明天天气", events=[]),
        business_client=business,
        call_mcp_tool=business.call_mcp_tool,
    )

    result = await skill.execute({}, ctx)

    assert result.ok
    assert calls == [
        ("search_cities", {"keyword": "北京市", "limit": 10}),
        ("get_weather", {"location": "北京市东城区"}),
    ]


@pytest.mark.asyncio
async def test_weather_skill_exposes_business_error() -> None:
    class Business:
        async def call_mcp_tool(
            self, name: str, arguments: dict, *, risk_level: str
        ) -> dict:
            return {"error": "fetch_failed", "message": "天气源暂时不可用"}

    skill = next(skill for skill in load_all() if skill.name == "get_weather")
    business = Business()
    ctx = SimpleNamespace(
        turn=SimpleNamespace(user_input="查询天气", events=[]),
        business_client=business,
        call_mcp_tool=business.call_mcp_tool,
    )

    result = await skill.execute({}, ctx)

    assert not result.ok
    assert result.error == "天气源暂时不可用"
