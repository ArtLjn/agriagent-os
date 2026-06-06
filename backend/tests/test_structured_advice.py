"""测试每日建议结构化返回 — AdviceItem schema + JSON 解析 + fallback。"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.agent import AdviceItem, DailyAdviceResponse
from app.services.agent_service import get_daily_advice, refresh_daily_advice


def _make_mock_db() -> MagicMock:
    """创建带 refresh side_effect 的 mock 数据库会话。"""
    mock_db = MagicMock()

    def _refresh_side_effect(record):
        record.created_at = datetime(2024, 1, 1, 12, 0, 0)

    mock_db.refresh.side_effect = _refresh_side_effect
    # 让缓存查询链式调用返回 None，确保走 LLM 路径
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    return mock_db


@pytest.fixture(autouse=True)
def mock_composer():
    """隔离 prompt 渲染，让结构化建议测试聚焦解析行为。"""
    with patch("app.services.agent_service.get_composer") as mock:
        mock.return_value.compose.return_value = "daily prompt"
        yield mock


# ---------- Schema 校验 ----------


class TestAdviceItemSchema:
    """测试 AdviceItem Pydantic 模型。"""

    def test_valid_advice_item(self) -> None:
        """正常字段构造 AdviceItem。"""
        item = AdviceItem(title="浇水", detail="土壤偏干需补水", priority=1, icon="💧")
        assert item.title == "浇水"
        assert item.priority == 1

    def test_title_exceeds_max_length_raises(self) -> None:
        """title 超过 15 字符时校验失败。"""
        with pytest.raises(Exception):
            AdviceItem(title="A" * 16, detail="ok", priority=1)

    def test_priority_out_of_range_raises(self) -> None:
        """priority 超出 1-3 范围时校验失败。"""
        with pytest.raises(Exception):
            AdviceItem(title="ok", detail="ok", priority=0)

    def test_priority_above_max_raises(self) -> None:
        """priority 大于 3 时校验失败。"""
        with pytest.raises(Exception):
            AdviceItem(title="ok", detail="ok", priority=4)

    def test_default_icon(self) -> None:
        """icon 默认值为 📋。"""
        item = AdviceItem(title="ok", detail="ok", priority=2)
        assert item.icon == "📋"


class TestDailyAdviceResponseSchema:
    """测试 DailyAdviceResponse 使用 items 字段。"""

    def test_items_field_works(self) -> None:
        """items 列表正确构造响应。"""
        items = [
            AdviceItem(title="浇水", detail="土壤偏干", priority=1),
            AdviceItem(title="施肥", detail="生长期需肥", priority=2),
        ]
        resp = DailyAdviceResponse(
            cycle_id=1,
            items=items,
            created_at=datetime(2024, 1, 1),
        )
        assert len(resp.items) == 2
        assert resp.items[0].title == "浇水"

    def test_advice_field_backward_compat(self) -> None:
        """advice 字段作为向后兼容的 computed property 返回第一条 detail。"""
        items = [
            AdviceItem(title="浇水", detail="土壤偏干需补水", priority=1),
            AdviceItem(title="施肥", detail="生长期", priority=2),
        ]
        resp = DailyAdviceResponse(
            cycle_id=1,
            items=items,
            created_at=datetime(2024, 1, 1),
        )
        # advice 属性应拼接所有条目
        assert isinstance(resp.advice, str)
        assert len(resp.advice) > 0

    def test_advice_empty_items(self) -> None:
        """items 为空列表时 advice 返回空字符串。"""
        resp = DailyAdviceResponse(
            cycle_id=None,
            items=[],
            created_at=datetime(2024, 1, 1),
        )
        assert resp.advice == ""


# ---------- JSON 解析成功 ----------


class TestDailyAdviceJsonParsing:
    """测试 LLM 返回合法 JSON 数组时的解析逻辑。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_json_array_parsed_to_items(self, mock_invoke: AsyncMock) -> None:
        """LLM 返回 JSON 数组时，正确解析为 AdviceItem 列表。"""
        mock_invoke.return_value = (
            "```json\n"
            '[{"title":"浇水","detail":"土壤偏干需补水","priority":1,"icon":"💧"},'
            '{"title":"施肥","detail":"生长期需追加氮肥","priority":2,"icon":"🌱"}]\n'
            "```"
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1)

        assert isinstance(result, DailyAdviceResponse)
        assert len(result.items) == 2
        assert result.items[0].title == "浇水"
        assert result.items[0].priority == 1
        assert result.items[1].title == "施肥"

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_items_sorted_by_priority(self, mock_invoke: AsyncMock) -> None:
        """items 按 priority 升序排列。"""
        mock_invoke.return_value = (
            '[{"title":"施肥","detail":"生长期","priority":3,"icon":"🌱"},'
            '{"title":"浇水","detail":"土壤偏干","priority":1,"icon":"💧"},'
            '{"title":"除草","detail":"杂草较多","priority":2,"icon":"🌾"}]'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1)

        priorities = [item.priority for item in result.items]
        assert priorities == sorted(priorities)
        assert result.items[0].title == "浇水"


# ---------- JSON 解析失败 fallback ----------


class TestDailyAdviceFallback:
    """测试 LLM 返回非 JSON 时的 fallback 逻辑。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_plain_text_fallback_single_item(
        self, mock_invoke: AsyncMock
    ) -> None:
        """LLM 返回纯文本时，fallback 为单条 AdviceItem。"""
        mock_invoke.return_value = "今天天气不错，建议给蔬菜浇水并追施氮肥。"
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1)

        assert len(result.items) == 1
        assert result.items[0].title == "今日农事建议"
        assert result.items[0].priority == 2
        assert result.items[0].icon == "📋"
        assert result.items[0].detail == "今天天气不错，建议给蔬菜浇水并追施氮肥。"[:50]

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_malformed_json_fallback(self, mock_invoke: AsyncMock) -> None:
        """LLM 返回畸形 JSON 时，fallback 为单条 AdviceItem。"""
        mock_invoke.return_value = "这不是 JSON 格式，就是一段纯文本建议。"
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1)

        assert len(result.items) == 1
        assert result.items[0].title == "今日农事建议"


# ---------- Title 截断 ----------


class TestTitleTruncation:
    """测试 title 超长时的截断逻辑。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_long_title_truncated(self, mock_invoke: AsyncMock) -> None:
        """title 超过 10 字时截断并添加省略号。"""
        long_title = "这是一个非常非常长的标题超过十个字"
        mock_invoke.return_value = (
            f'[{{"title":"{long_title}","detail":"ok","priority":1,"icon":"📋"}}]'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1)

        assert len(result.items) == 1
        # 截断后 title <= 15 字符（10字 + "…" = 11字符，在 max_length=15 内）
        assert result.items[0].title.endswith("…")
        assert len(result.items[0].title) <= 15


# ---------- refresh_daily_advice ----------


class TestRefreshDailyAdvice:
    """测试强制刷新每日建议。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_refresh_returns_structured_items(
        self, mock_invoke: AsyncMock
    ) -> None:
        """refresh_daily_advice 也返回结构化 items。"""
        mock_invoke.return_value = (
            '[{"title":"防虫","detail":"近期蚜虫高发","priority":1,"icon":"🐛"}]'
        )
        mock_db = _make_mock_db()

        result = await refresh_daily_advice(mock_db, farm_id=1)

        assert isinstance(result, DailyAdviceResponse)
        assert len(result.items) == 1
        assert result.items[0].title == "防虫"


# ---------- cycle_id 传递 ----------


class TestCycleIdPassthrough:
    """测试 cycle_id 正确传递到记录和响应。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_cycle_id_in_response(self, mock_invoke: AsyncMock) -> None:
        """返回的 DailyAdviceResponse 包含正确的 cycle_id。"""
        mock_invoke.return_value = (
            '[{"title":"采收","detail":"番茄已成熟","priority":1,"icon":"🍅"}]'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, cycle_id=42, farm_id=1)

        assert result.cycle_id == 42
        assert result.items[0].title == "采收"
