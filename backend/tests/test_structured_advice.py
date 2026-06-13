"""测试每日建议结构化返回 — AdviceItem schema + v2 响应兼容。"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas.agent import AdviceItem, DailyAdviceResponse
from app.services.agent_service import get_daily_advice, refresh_daily_advice
from app.services.daily_advice_models import DailyAdviceCandidate


def _candidate() -> DailyAdviceCandidate:
    return DailyAdviceCandidate(
        id="weather:hot",
        category="weather",
        title_hint="高温错峰采收",
        detail_hint="今天最高温较高，建议避开中午高温时段安排采收。",
        priority=2,
        due_date=None,
        source_type="weather_service",
        source_id=12,
        dedupe_key="weather:hot",
        reason="天气服务命中高温规则",
    )


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

    def test_legacy_title_at_max_length_passes_without_compact(self) -> None:
        """旧字段输入没有 compact 时仍按旧 title 长度约束校验。"""
        item = AdviceItem(title="A" * 15, detail="ok", priority=1)
        assert item.title == "A" * 15
        assert item.detail == "ok"

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

    def test_compact_only_defaults_priority(self) -> None:
        """v2 compact-only 输入缺省 priority 时默认常规优先级。"""
        item = AdviceItem(
            compact={
                "title": "巡田记录",
                "subtitle": "建议今天完成一次基础巡田并补齐记录。",
                "icon": "NotebookPen",
                "icon_color": "slate",
            },
        )

        assert item.priority == 3
        assert item.title == "巡田记录"
        assert item.detail == "建议今天完成一次基础巡田并补齐记录。"

    def test_compact_input_keeps_outer_priority(self) -> None:
        """v2 compact 输入存在外层 priority 时保留外层值。"""
        item = AdviceItem(
            priority=1,
            compact={
                "title": "高温错峰",
                "subtitle": "今天高温明显，建议避开中午时段安排作业。",
                "icon": "CloudSun",
                "icon_color": "amber",
                "priority": 3,
            },
        )

        assert item.priority == 1


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


class TestDailyAdviceV2Empty:
    """测试无候选时的 v2 empty 响应。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_empty_candidates_do_not_call_llm(
        self, mock_invoke: AsyncMock
    ) -> None:
        """没有候选时不让 LLM 自造建议，返回可展示 empty 结构。"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.core.database import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        with patch(
            "app.services.daily_advice_generation.collect_daily_advice_candidates",
            new_callable=AsyncMock,
        ) as mock_collect:
            mock_collect.return_value = []
            result = await get_daily_advice(session, farm_id=1)

        mock_invoke.assert_not_called()
        assert isinstance(result, DailyAdviceResponse)
        assert result.generation.mode == "empty"
        assert result.items[0].id == "empty-today"
        session.close()


# ---------- JSON 解析失败 fallback ----------


class TestDailyAdviceFallback:
    """测试 v2 生成失败时的候选 skeleton fallback。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_plain_text_fallback_uses_candidate_skeleton(
        self, mock_invoke: AsyncMock
    ) -> None:
        """LLM 返回纯文本时，fallback 不采纳纯文本，使用候选骨架。"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.core.database import Base

        mock_invoke.return_value = "这不是 JSON 格式，就是一段纯文本建议。"
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        candidate = _candidate()
        with patch(
            "app.services.daily_advice_generation.collect_daily_advice_candidates",
            new_callable=AsyncMock,
        ) as mock_collect:
            mock_collect.return_value = [candidate]
            result = await get_daily_advice(session, farm_id=1)

        assert mock_invoke.await_count == 3
        assert result.generation.mode == "fallback"
        assert result.items[0].id == candidate.id
        assert result.items[0].title == "高温错峰采收"
        session.close()


# ---------- refresh_daily_advice ----------


class TestRefreshDailyAdvice:
    """测试强制刷新每日建议。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_refresh_returns_structured_items(
        self, mock_invoke: AsyncMock
    ) -> None:
        """refresh_daily_advice 也返回 v2 结构化 items。"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.core.database import Base

        mock_invoke.return_value = "bad json"
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        with patch(
            "app.services.daily_advice_generation.collect_daily_advice_candidates",
            new_callable=AsyncMock,
        ) as mock_collect:
            mock_collect.return_value = [_candidate()]
            result = await refresh_daily_advice(session, farm_id=1)

        assert mock_invoke.await_count == 3
        assert isinstance(result, DailyAdviceResponse)
        assert len(result.items) == 1
        assert result.items[0].detail_view is not None
        session.close()


# ---------- cycle_id 传递 ----------


class TestCycleIdPassthrough:
    """测试 cycle_id 正确传递到记录和响应。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_cycle_id_in_response(self, mock_invoke: AsyncMock) -> None:
        """返回的 DailyAdviceResponse 包含正确的 cycle_id。"""
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from app.core.database import Base

        mock_invoke.return_value = "bad json"
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=engine)
        session = sessionmaker(bind=engine)()
        with patch(
            "app.services.daily_advice_generation.collect_daily_advice_candidates",
            new_callable=AsyncMock,
        ) as mock_collect:
            mock_collect.return_value = [_candidate()]
            result = await get_daily_advice(session, cycle_id=42, farm_id=1)

        assert result.cycle_id == 42
        assert result.items[0].title == "高温错峰采收"
        session.close()
