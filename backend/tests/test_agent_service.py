from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    return mock_db


class TestChatWithAgent:
    """测试 Agent 对话服务。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_chat_with_agent_returns_reply(self, mock_invoke: AsyncMock) -> None:
        """验证对话返回回复并保存记录。"""
        mock_invoke.return_value = "建议：今天浇水。"
        mock_db = _make_mock_db()

        result = await chat_with_agent(mock_db, "今天做什么？", farm_id=1)

        assert result.reply == "建议：今天浇水。"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    @patch("app.services.agent_service.save_message")
    @patch("app.services.agent_service.get_or_create_conversation")
    async def test_chat_with_session_id_saves_messages(
        self,
        mock_get_conv: MagicMock,
        mock_save_msg: MagicMock,
        mock_invoke: AsyncMock,
    ) -> None:
        """验证 session_id 存在时保存用户和助手消息到会话。"""
        mock_invoke.return_value = "回复内容"
        mock_conv = MagicMock()
        mock_conv.id = 42
        mock_get_conv.return_value = mock_conv
        mock_db = _make_mock_db()

        result = await chat_with_agent(
            mock_db, "你好", farm_id=1, session_id="sess-123"
        )

        assert result.reply == "回复内容"
        # 验证 get_or_create_conversation 被调用
        mock_get_conv.assert_called_once_with(mock_db, 1, "sess-123", user_id=None)
        # 验证 save_message 被调用 2 次：user + assistant
        assert mock_save_msg.call_count == 2
        mock_save_msg.assert_any_call(mock_db, 42, "user", "你好")
        mock_save_msg.assert_any_call(mock_db, 42, "assistant", "回复内容")

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    @patch("app.services.agent_service.save_message")
    @patch("app.services.agent_service.get_or_create_conversation")
    async def test_chat_with_session_id_passes_conversation_id_to_advisor(
        self,
        mock_get_conv: MagicMock,
        mock_save_msg: MagicMock,
        mock_invoke: AsyncMock,
    ) -> None:
        """验证 session_id 时 conversation_id 传递给 invoke_advisor。"""
        mock_invoke.return_value = "回复"
        mock_conv = MagicMock()
        mock_conv.id = 99
        mock_get_conv.return_value = mock_conv
        mock_db = _make_mock_db()

        await chat_with_agent(mock_db, "问题", farm_id=1, session_id="sess-abc")

        # invoke_advisor 应该被传入 db 和 conversation_id
        mock_invoke.assert_called_once()
        call_kwargs = mock_invoke.call_args
        assert (
            call_kwargs.kwargs.get("db") == mock_db
            or call_kwargs[1].get("db") == mock_db
        )

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    @patch("app.services.agent_service.save_message")
    async def test_chat_without_session_id_no_conversation(
        self, mock_save_msg: MagicMock, mock_invoke: AsyncMock
    ) -> None:
        """验证无 session_id 时不保存会话消息。"""
        mock_invoke.return_value = "回复"
        mock_db = _make_mock_db()

        result = await chat_with_agent(mock_db, "问题", farm_id=1)

        assert result.reply == "回复"
        mock_save_msg.assert_not_called()

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    @patch("app.services.agent_service.save_message")
    @patch("app.services.agent_service.get_or_create_conversation")
    async def test_chat_pending_confirm_saves_to_conversation(
        self,
        mock_get_conv: MagicMock,
        mock_save_msg: MagicMock,
        mock_invoke: AsyncMock,
    ) -> None:
        """验证 pending action 确认路径也保存会话消息。"""
        from app.infra.pending_actions import store_pending, remove_pending

        mock_conv = MagicMock()
        mock_conv.id = 10
        mock_get_conv.return_value = mock_conv

        # 清理：确保无残留 pending
        remove_pending(1)
        store_pending(1, "create_cost_record", {"amount": 100})

        mock_db = _make_mock_db()
        # mock execute 相关
        with patch(
            "app.services.agent_service._execute_pending_action",
            new_callable=AsyncMock,
        ) as mock_exec:
            mock_exec.return_value = "已记账"
            result = await chat_with_agent(
                mock_db, "确认", farm_id=1, session_id="sess-confirm"
            )

        assert "已记账" in result.reply or "已执行" in result.reply
        # 应该保存 user + assistant 消息
        assert mock_save_msg.call_count == 2
        mock_save_msg.assert_any_call(mock_db, 10, "user", "确认")

        # 清理
        remove_pending(1)


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


class TestGetDailyAdvice:
    """测试每日建议服务。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_returns_structured_items(
        self, mock_invoke: AsyncMock
    ) -> None:
        """验证每日建议生成结构化 items 并保存（旧数组格式）。"""
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
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_new_format_with_preview(
        self, mock_invoke: AsyncMock
    ) -> None:
        """验证新格式（含 preview + items）正确解析。"""
        mock_invoke.return_value = (
            '{"preview":"今日需浇水","items":['
            '{"title":"浇水","detail":"土壤干燥需补水","priority":1,"icon":"💧"}'
            ']}'
        )
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, farm_id=1, cycle_id=1)

        assert result.preview == "今日需浇水"
        assert len(result.items) == 1
        assert result.items[0].title == "浇水"
        assert result.items[0].icon == "💧"

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_old_format_backward_compatible(
        self, mock_invoke: AsyncMock
    ) -> None:
        """验证旧数组格式仍然兼容。"""
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
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_fallback_on_plain_text(
        self, mock_invoke: AsyncMock
    ) -> None:
        """验证 LLM 返回纯文本时 fallback 为单条 item。"""
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
    @patch("app.services.agent_service.generate_cycle_report", new_callable=AsyncMock)
    async def test_generate_report_returns_content(
        self, mock_generate: AsyncMock
    ) -> None:
        """验证报告生成并保存。"""
        mock_generate.return_value = "报告内容..."
        mock_db = _make_mock_db()

        result = await generate_report(
            mock_db, farm_id=1, cycle_id=1, report_type="weekly"
        )

        assert result.content == "报告内容..."
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
