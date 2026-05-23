from unittest.mock import MagicMock, patch

from app.core.llm import get_llm


class TestGetLlm:
    """测试 LLM 客户端工厂。"""

    @patch("app.core.llm.ChatOpenAI")
    def test_get_llm_returns_chat_openai_instance(self, mock_chat_openai: MagicMock) -> None:
        """验证 get_llm 返回 ChatOpenAI 实例。"""
        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        llm = get_llm()

        assert llm is mock_instance
        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args.kwargs
        assert call_kwargs["model"] == "qwen3.5-plus-2026-04-20"
        assert call_kwargs["api_key"] == ""
        assert call_kwargs["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
