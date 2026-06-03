"""测试 _llm_node 中 UserSetting.default_city 的优先级逻辑。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.graph import _llm_node
from app.agent.prompt_cache import clear_all_caches


class _FakeFarm:
    def __init__(self, user_id: str | None, location: str = ""):
        self.id = 1
        self.user_id = user_id
        self.location = location


class _FakeUser:
    def __init__(self, nickname: str = "农友"):
        self.id = "u1"
        self.nickname = nickname


class _FakeUserSetting:
    def __init__(
        self,
        default_city: str | None,
        default_lat: float | None = None,
        default_lon: float | None = None,
    ):
        self.user_id = "u1"
        self.default_city = default_city
        self.default_lat = default_lat
        self.default_lon = default_lon


def _make_query_side_effect(*results):
    """构造 db.query().filter().first() 的链式调用返回值。"""

    class FirstCaller:
        """跨所有 query 调用共享的计数器，按调用顺序依次返回结果。"""

        def __init__(self, vals):
            self._vals = vals
            self._idx = 0

        def first(self):
            if self._idx < len(self._vals):
                v = self._vals[self._idx]
                self._idx += 1
                return v
            return None

    caller = FirstCaller(list(results))

    def _side_effect(model):
        mock_q = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first = caller.first
        mock_q.filter.return_value = mock_filter
        return mock_q

    return _side_effect


def _build_mock_session(*query_results):
    """创建模拟的 db session，自动处理 query 链式调用。"""
    mock_session = MagicMock()
    mock_session.query.side_effect = _make_query_side_effect(*query_results)
    return mock_session


@pytest.fixture()
def mock_env():
    """mock 掉所有外部依赖：LLM、collector、quota、prompt 渲染等。"""
    clear_all_caches()
    with (
        patch("app.agent.runtime.nodes.get_llm") as mock_get_llm,
        patch("app.agent.runtime.nodes.get_langchain_tools") as mock_get_tools,
        patch("app.agent.runtime.nodes.get_composer") as mock_get_composer,
        patch("app.agent.runtime.nodes.get_collector") as mock_get_collector,
        patch("app.agent.runtime.nodes.get_request_date") as mock_get_date,
        patch("app.agent.runtime.nodes.check_quota", return_value=True),
        patch("app.agent.runtime.nodes.select_tools", return_value=[]),
        patch("app.agent.runtime.nodes._get_classifier", return_value=None),
    ):
        mock_get_tools.return_value = []
        mock_get_date.return_value = __import__("datetime").date(2026, 5, 29)
        mock_composer = MagicMock()
        mock_composer.compose.return_value = "system prompt"
        mock_get_composer.return_value = mock_composer
        mock_get_collector.return_value = MagicMock()
        llm = MagicMock()
        llm.model_name = "test-model"
        llm.bind_tools.return_value = llm
        llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content="回复",
                tool_calls=[],
                response_metadata={"token_usage": {"total_tokens": 10}},
            ),
        )
        mock_get_llm.return_value = llm
        yield mock_composer.compose
    clear_all_caches()


async def _run_llm_node(mock_render, *query_results):
    """运行 _llm_node 并返回 render_prompt 的 variables。"""
    mock_session = _build_mock_session(*query_results)
    with patch("app.agent.runtime.llm_support.SessionLocal", return_value=mock_session):
        state = {"messages": [], "farm_id": 1}
        await _llm_node(state)
    _, kwargs = mock_render.call_args
    return kwargs["variables"]


# ── 正常流程 ──────────────────────────────────────────────────


class TestUserSettingCityPriority:
    """验证 UserSetting.default_city 优先于 Farm.location。"""

    @pytest.mark.asyncio
    async def test_user_setting_city_takes_priority(self, mock_env):
        """用户设置了 default_city 时，farm_location 应使用 default_city。"""
        farm = _FakeFarm(user_id="u1", location="旧农场地址")
        user = _FakeUser(nickname="张三")
        user_setting = _FakeUserSetting(default_city="广州")

        variables = await _run_llm_node(mock_env, farm, user, user_setting)
        assert variables["farm_location"] == "广州"

    @pytest.mark.asyncio
    async def test_fallback_to_farm_location(self, mock_env):
        """UserSetting 无 default_city 时，farm_location 回退到 Farm.location。"""
        farm = _FakeFarm(user_id="u1", location="农场地址")
        user = _FakeUser(nickname="李四")
        user_setting = _FakeUserSetting(default_city=None)

        variables = await _run_llm_node(mock_env, farm, user, user_setting)
        assert variables["farm_location"] == "农场地址"

    @pytest.mark.asyncio
    async def test_no_user_setting_record(self, mock_env):
        """UserSetting 记录不存在时，回退到 Farm.location。"""
        farm = _FakeFarm(user_id="u1", location="农场地址")
        user = _FakeUser(nickname="王五")

        variables = await _run_llm_node(mock_env, farm, user, None)
        assert variables["farm_location"] == "农场地址"


# ── 边界情况 ──────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_no_farm_record(self, mock_env):
        """Farm 记录不存在时，farm_location 为空字符串。"""
        variables = await _run_llm_node(mock_env, None)
        assert variables["farm_location"] == ""

    @pytest.mark.asyncio
    async def test_farm_no_user_id(self, mock_env):
        """Farm 存在但 user_id 为 None 时，farm_location 用 Farm.location。"""
        farm = _FakeFarm(user_id=None, location="某个农场")

        variables = await _run_llm_node(mock_env, farm)
        assert variables["farm_location"] == "某个农场"

    @pytest.mark.asyncio
    async def test_user_setting_empty_string_city(self, mock_env):
        """UserSetting.default_city 为空字符串时，回退到 Farm.location。"""
        farm = _FakeFarm(user_id="u1", location="农场地址")
        user = _FakeUser(nickname="赵六")
        user_setting = _FakeUserSetting(default_city="")

        variables = await _run_llm_node(mock_env, farm, user, user_setting)
        assert variables["farm_location"] == "农场地址"
