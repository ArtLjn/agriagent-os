"""测试 _llm_node 混合 ToolMessage 三路分支处理。"""

import pytest
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, ToolMessage

from app.agent.graph import _llm_node
from app.infra.pending_actions import PENDING_MARKER


class TestMixedToolMessages:
    """测试混合 pending + normal ToolMessage 的合并逻辑。"""

    @pytest.mark.asyncio
    async def test_mixed_returns_combined_content(self):
        """pending + normal 混合时，返回包含两部分内容的 AIMessage。"""
        normal_msg = ToolMessage(
            content="今天天气：晴，25°C，湿度60%，东南风3级。",
            tool_call_id="tc_weather",
        )
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 🌱 确认创建茬口：玉米 春季，确认吗？",
            tool_call_id="tc_crop",
        )
        state = {
            "messages": [normal_msg, pending_msg],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        assert isinstance(ai_msg, AIMessage)
        # query 结果应包含在回复中
        assert "晴" in ai_msg.content
        assert "25°C" in ai_msg.content
        # confirm 提示应包含在回复中
        assert "确认" in ai_msg.content
        assert "玉米" in ai_msg.content

    @pytest.mark.asyncio
    async def test_mixed_does_not_call_llm(self):
        """混合场景下不应调用 LLM。"""
        from unittest.mock import patch

        normal_msg = ToolMessage(
            content="本月支出：2000元",
            tool_call_id="tc_summary",
        )
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 50元 支出，确认吗？",
            tool_call_id="tc_cost",
        )
        state = {
            "messages": [normal_msg, pending_msg],
            "farm_id": 1,
        }

        with patch("app.agent.graph.get_llm") as mock_get_llm:
            result = await _llm_node(state)
            assert isinstance(result["messages"][0], AIMessage)
            mock_get_llm.assert_not_called()


class TestPurePendingPath:
    """测试纯 pending ToolMessage 路径不变。"""

    @pytest.mark.asyncio
    async def test_pure_pending_returns_confirm_only(self):
        """只有 pending ToolMessage 时，仅返回确认文案（不变）。"""
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 200元 支出，确认吗？",
            tool_call_id="tc_cost",
        )
        state = {
            "messages": [pending_msg],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        assert isinstance(ai_msg, AIMessage)
        assert "确认记账" in ai_msg.content
        assert "化肥" in ai_msg.content
        assert PENDING_MARKER not in ai_msg.content

    @pytest.mark.asyncio
    async def test_multiple_pending_returns_last(self):
        """多个 pending ToolMessage 时，返回最后一个的确认文案（不变）。"""
        pending1 = ToolMessage(
            content=f"{PENDING_MARKER} 🌱 确认创建茬口：玉米，确认吗？",
            tool_call_id="tc1",
        )
        pending2 = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 50元 支出，确认吗？",
            tool_call_id="tc2",
        )
        state = {
            "messages": [pending1, pending2],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        # 纯 pending 路径取最后一个
        assert "确认记账" in ai_msg.content


class TestPureNormalPath:
    """测试纯 normal ToolMessage 路径不变（正常走 LLM）。"""

    @pytest.mark.asyncio
    async def test_pure_normal_does_not_early_return(self):
        """只有 normal ToolMessage 时，不提前返回（走 LLM 流程）。"""
        from unittest.mock import AsyncMock, patch

        normal_msg = ToolMessage(
            content="本月支出：2000元",
            tool_call_id="tc_summary",
        )
        state = {
            "messages": [normal_msg],
            "farm_id": 1,
        }

        # 需要完整 mock 因为会走 LLM
        with (
            patch("app.agent.graph.get_llm") as mock_get_llm,
            patch("app.agent.graph.get_langchain_tools", return_value=[]),
            patch("app.agent.graph.get_composer") as mock_get_composer,
            patch("app.agent.graph.get_request_date") as mock_get_date,
            patch("app.agent.graph.get_collector") as mock_collector,
            patch("app.agent.graph.check_quota", return_value=True),
            patch("app.agent.graph.select_tools", return_value=[]),
            patch("app.agent.graph._get_classifier", return_value=None),
            patch("app.agent.graph.SessionLocal") as mock_session,
        ):
            mock_get_date.return_value = __import__("datetime").date(2026, 5, 30)
            mock_composer = MagicMock()
            mock_composer.compose.return_value = "system prompt"
            mock_get_composer.return_value = mock_composer
            mock_collector.return_value = MagicMock()

            # mock db query chain
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value = mock_db

            # mock LLM
            llm = MagicMock()
            llm.model_name = "test-model"
            mock_response = MagicMock(spec=AIMessage)
            mock_response.content = "LLM 回复"
            mock_response.tool_calls = []
            mock_response.response_metadata = {"token_usage": {"total_tokens": 10}}
            llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = llm

            result = await _llm_node(state)
            ai_msg = result["messages"][0]

            assert ai_msg.content == "LLM 回复"
            # 验证 LLM 确实被调用了
            llm.ainvoke.assert_called_once()


class TestMixedEdgeCases:
    """混合场景边界情况。"""

    @pytest.mark.asyncio
    async def test_normal_content_truncated_at_200(self):
        """normal ToolMessage 内容超 200 字符时截断。"""
        long_content = "天气详情：" + "晴，" * 200  # 远超 200 字符
        normal_msg = ToolMessage(
            content=long_content,
            tool_call_id="tc_weather",
        )
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 50元 支出，确认吗？",
            tool_call_id="tc_cost",
        )
        state = {
            "messages": [normal_msg, pending_msg],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        # normal 内容应被截断，不应包含完整的 1000+ 字符
        assert (
            len(
                [
                    line
                    for line in ai_msg.content.split("\n")
                    if "天气" in line and "晴" in line
                ][0]
            )
            <= 250
        )

    @pytest.mark.asyncio
    async def test_error_normal_tool_still_included(self):
        """normal ToolMessage 内容是错误信息时仍然包含。"""
        error_msg = ToolMessage(
            content="工具调用失败: 天气服务不可用",
            tool_call_id="tc_weather",
        )
        pending_msg = ToolMessage(
            content=f"{PENDING_MARKER} 💰 确认记账：化肥 50元 支出，确认吗？",
            tool_call_id="tc_cost",
        )
        state = {
            "messages": [error_msg, pending_msg],
            "farm_id": 1,
        }

        result = await _llm_node(state)
        ai_msg = result["messages"][0]

        assert "工具调用失败" in ai_msg.content
        assert "确认记账" in ai_msg.content

    @pytest.mark.asyncio
    async def test_empty_messages_returns_normally(self):
        """空消息列表不应在 pending 分支报错。"""
        from unittest.mock import AsyncMock, patch

        state = {"messages": [], "farm_id": 1}

        with (
            patch("app.agent.graph.get_llm") as mock_get_llm,
            patch("app.agent.graph.get_langchain_tools", return_value=[]),
            patch("app.agent.graph.get_composer") as mock_get_composer,
            patch("app.agent.graph.get_request_date") as mock_get_date,
            patch("app.agent.graph.get_collector") as mock_collector,
            patch("app.agent.graph.check_quota", return_value=True),
            patch("app.agent.graph.select_tools", return_value=[]),
            patch("app.agent.graph._get_classifier", return_value=None),
            patch("app.agent.graph.SessionLocal") as mock_session,
        ):
            mock_get_date.return_value = __import__("datetime").date(2026, 5, 30)
            mock_composer = MagicMock()
            mock_composer.compose.return_value = "system prompt"
            mock_get_composer.return_value = mock_composer
            mock_collector.return_value = MagicMock()

            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value = mock_db

            llm = MagicMock()
            llm.model_name = "test-model"
            mock_response = MagicMock(spec=AIMessage)
            mock_response.content = "你好"
            mock_response.tool_calls = []
            mock_response.response_metadata = {"token_usage": {"total_tokens": 5}}
            llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_get_llm.return_value = llm

            result = await _llm_node(state)
            assert result["messages"][0].content == "你好"
