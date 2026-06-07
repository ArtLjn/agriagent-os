from datetime import datetime
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.agent import ChatRequest
from app.services.agent_service import (
    chat_with_agent,
    get_daily_advice,
    generate_report,
)


def _make_mock_db() -> MagicMock:
    """创建带 refresh side_effect 的 mock 数据库会话。"""
    mock_db = MagicMock()

    def _refresh_side_effect(record):
        record.created_at = datetime(2024, 1, 1, 12, 0, 0)

    mock_db.refresh.side_effect = _refresh_side_effect
    # 让缓存查询链式调用返回 None，确保走 LLM 路径
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    mock_db.query.return_value.filter.return_value.first.return_value = None
    return mock_db


def _make_report_data():
    from app.services.report_data_service import ReportData

    return ReportData(
        report_type="weekly",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 7),
        overview={
            "active_cycles": 1,
            "log_count": 0,
            "total_cost": "0",
            "total_income": "0",
            "net_profit": "0",
        },
        cycles=[],
        costs=[],
        logs=[],
    )


class TestChatWithAgent:
    """测试 Agent 对话服务。"""

    @pytest.mark.asyncio
    async def test_chat_with_agent_delegates_to_application_use_case(self) -> None:
        """验证兼容入口委托 Application 聊天用例。"""
        mock_db = _make_mock_db()
        farm = MagicMock()
        farm.id = 1
        farm.user_id = "user-1"

        with (
            patch(
                "app.services.agent_service._load_farm_for_application",
                return_value=farm,
            ) as mock_load_farm,
            patch(
                "app.services.agent_service.application_chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = MagicMock(reply="应用层回复")
            result = await chat_with_agent(
                mock_db,
                "你好",
                farm_id=1,
                cycle_id=2,
                session_id="sess-1",
                user_id="user-1",
                request_id="req-1",
            )

        assert result.reply == "应用层回复"
        mock_load_farm.assert_called_once_with(mock_db, 1)
        mock_chat.assert_awaited_once()
        delegated_db, delegated_request, delegated_farm = mock_chat.call_args.args
        assert delegated_db == mock_db
        assert delegated_request == ChatRequest(
            message="你好", cycle_id=2, session_id="sess-1"
        )
        assert delegated_farm.id == farm.id
        assert delegated_farm.user_id == "user-1"
        assert mock_chat.call_args.kwargs == {"request_id": "req-1"}

    @pytest.mark.asyncio
    async def test_chat_with_agent_backfills_user_id_on_loaded_farm(self) -> None:
        """验证旧入口传入 user_id 时回填无用户农场。"""
        mock_db = _make_mock_db()
        farm = MagicMock()
        farm.id = 1
        farm.user_id = None

        with (
            patch(
                "app.services.agent_service._load_farm_for_application",
                return_value=farm,
            ),
            patch(
                "app.services.agent_service.application_chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = MagicMock(reply="回复内容")
            result = await chat_with_agent(
                mock_db,
                "你好",
                farm_id=1,
                session_id="sess-123",
                user_id="user-1",
            )

        assert result.reply == "回复内容"
        mock_chat.assert_awaited_once()
        delegated_farm = mock_chat.call_args.args[2]
        assert delegated_farm.id == farm.id
        assert delegated_farm.user_id == "user-1"
        assert farm.user_id is None

    @pytest.mark.asyncio
    async def test_chat_with_agent_explicit_user_id_overrides_farm_user_id(
        self,
    ) -> None:
        """验证显式 user_id 优先于农场原有 user_id。"""
        mock_db = _make_mock_db()
        farm = MagicMock()
        farm.id = 1
        farm.user_id = "farm-user"

        with (
            patch(
                "app.services.agent_service._load_farm_for_application",
                return_value=farm,
            ),
            patch(
                "app.services.agent_service.application_chat",
                new_callable=AsyncMock,
            ) as mock_chat,
        ):
            mock_chat.return_value = MagicMock(reply="回复内容")
            await chat_with_agent(
                mock_db,
                "你好",
                farm_id=1,
                session_id="sess-123",
                user_id="explicit-user",
            )

        delegated_farm = mock_chat.call_args.args[2]
        assert delegated_farm.user_id == "explicit-user"
        assert farm.user_id == "farm-user"

    @pytest.mark.asyncio
    async def test_load_farm_for_application_raises_when_missing(self) -> None:
        """验证兼容入口加载不到农场时抛出明确错误。"""
        from app.services.agent_service import _load_farm_for_application

        mock_db = _make_mock_db()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ValueError, match="未找到农场: 1"):
            _load_farm_for_application(mock_db, 1)

        mock_db.query.assert_called_once()


class TestStreamChatWithAgent:
    """测试流式对话服务。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.stream_advisor")
    @patch("app.services.agent_service.save_message")
    @patch("app.services.agent_service.get_or_create_conversation")
    async def test_stream_with_session_id_saves_messages(
        self,
        mock_get_conv: MagicMock,
        mock_save_msg: MagicMock,
        mock_stream: MagicMock,
    ) -> None:
        """验证流式对话也保存消息到会话。"""
        mock_conv = MagicMock()
        mock_conv.id = 55
        mock_get_conv.return_value = mock_conv

        async def _fake_stream(*args, **kwargs):
            yield "chunk1"
            yield "chunk2"

        mock_stream.side_effect = _fake_stream
        mock_db = _make_mock_db()

        from app.services.agent_service import stream_chat_with_agent

        chunks = []
        async for chunk in stream_chat_with_agent(
            "问题", farm_id=1, db=mock_db, session_id="sess-stream"
        ):
            chunks.append(chunk)

        assert chunks == ["chunk1", "chunk2"]
        # 验证保存 user 消息（assistant 由调用方 agent.py 保存）
        mock_save_msg.assert_any_call(mock_db, 55, "user", "问题")

    @pytest.mark.asyncio
    async def test_stream_cycle_confirm_missing_template_creates_template_pending(
        self,
    ) -> None:
        """流式确认创建茬口但缺模板时，也应先请求确认创建模板。"""
        from app.infra.pending_actions import get_pending, remove_pending, store_pending
        from app.services.agent_service import stream_chat_with_agent

        remove_pending(1)
        store_pending(
            1,
            "create_crop_cycle",
            {"crop_name": "小麦"},
            original_input="我想种小麦",
        )

        with patch(
            "app.agent.executor.pending_actions._execute_write_skill",
            new_callable=AsyncMock,
        ) as mock_execute:
            mock_execute.return_value = "系统还没有小麦模板，要帮你创建一个吗？"
            chunks = []
            async for chunk in stream_chat_with_agent("确认", farm_id=1):
                chunks.append(chunk)

        reply = "".join(chunks)
        pending = get_pending(1)
        assert pending is not None
        assert pending.skill_name == "create_crop_template"
        assert pending.params == {"crop_name": "小麦"}
        assert pending.follow_up_skill_name == "create_crop_cycle"
        assert pending.follow_up_params == {"crop_name": "小麦"}
        assert "系统还没有小麦作物模板" in reply
        assert "确认创建作物模板" in reply
        assert "已执行：系统还没有" not in reply
        assert "crop_name" not in reply

        remove_pending(1)


class TestGetDailyAdvice:
    """测试每日建议服务。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_returns_structured_items(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """验证每日建议生成结构化 items 并保存（旧数组格式）。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '[{"title":"施肥","detail":"生长期需追肥","priority":1,"icon":"🌱"}]'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert len(result.items) == 1
        assert result.items[0].title == "施肥"
        assert result.preview == ""
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_passes_trusted_user_context(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """每日建议调用 Agent 时应携带可信 user_id，避免 quota 身份拦截。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '[{"title":"巡田","detail":"检查长势","priority":1,"icon":"📋"}]'
        )
        mock_db = _make_mock_db()
        farm = MagicMock()
        farm.user_id = "user-1"
        mock_db.query.return_value.filter.return_value.first.return_value = farm

        await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        mock_invoke.assert_awaited_once_with(
            "daily prompt",
            farm_id=1,
            db=mock_db,
            user_id="user-1",
            call_type="daily_advice",
        )

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_new_format_with_preview(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """验证新格式（含 preview + items）正确解析。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '{"preview":"今日需浇水","items":['
            '{"title":"浇水","detail":"土壤干燥需补水","priority":1,"icon":"💧"}'
            "]}"
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert result.preview == "今日需浇水"
        assert len(result.items) == 1
        assert result.items[0].title == "浇水"
        assert result.items[0].icon == "💧"

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_old_format_backward_compatible(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """验证旧数组格式仍然兼容。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = (
            '[{"title":"除草","detail":"杂草影响生长","priority":2,"icon":"🌿"},'
            '{"title":"施肥","detail":"补充氮肥","priority":1,"icon":"🌱"}]'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert result.preview == ""
        assert len(result.items) == 2
        # 按 priority 排序
        assert result.items[0].priority == 1
        assert result.items[0].title == "施肥"
        assert result.items[1].priority == 2
        assert result.items[1].title == "除草"

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_composer")
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_fallback_on_plain_text(
        self, mock_invoke: AsyncMock, mock_get_composer: MagicMock
    ) -> None:
        """验证 LLM 返回纯文本时 fallback 为单条 item。"""
        mock_get_composer.return_value.compose.return_value = "daily prompt"
        mock_invoke.return_value = "今日建议：施肥。"
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert len(result.items) == 1
        assert result.items[0].title == "今日农事建议"
        assert result.preview == ""
        # 向后兼容：advice property 返回拼接文本
        assert "今日建议：施肥。" in result.advice


class TestGenerateReport:
    """测试报告生成服务。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.get_llm")
    @patch("app.services.report_data_service.get_weekly_report_data")
    async def test_generate_report_returns_content(
        self, mock_report_data: AsyncMock, mock_get_llm: MagicMock
    ) -> None:
        """验证报告生成并保存。"""
        mock_report_data.return_value = _make_report_data()
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='{"summary":"报告内容...","advice_items":[]}'
            )
        )
        mock_get_llm.return_value = mock_llm
        mock_db = _make_mock_db()

        result = await generate_report(
            mock_db, farm_id=1, cycle_id=1, report_type="weekly"
        )

        assert "报告内容..." in result.content
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
