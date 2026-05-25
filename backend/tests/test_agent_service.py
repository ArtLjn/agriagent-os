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

        result = await chat_with_agent(mock_db, "今天做什么？")

        assert result.reply == "建议：今天浇水。"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestGetDailyAdvice:
    """测试每日建议服务。"""

    @pytest.mark.asyncio
    @patch("app.services.agent_service.invoke_advisor", new_callable=AsyncMock)
    async def test_get_daily_advice_returns_advice(
        self, mock_invoke: AsyncMock
    ) -> None:
        """验证每日建议生成并保存。"""
        mock_invoke.return_value = "今日建议：施肥。"
        mock_db = _make_mock_db()

        result = await get_daily_advice(mock_db, cycle_id=1)

        assert result.advice == "今日建议：施肥。"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


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

        result = await generate_report(mock_db, cycle_id=1, report_type="weekly")

        assert result.content == "报告内容..."
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
