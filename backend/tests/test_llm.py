from unittest.mock import MagicMock, patch

import pytest

from app.core.llm import LlmNotConfiguredError


class TestGetLlm:
    """测试 LLM 客户端工厂。"""

    @patch("app.core.llm.settings")
    def test_get_llm_raises_when_api_key_empty(self, mock_settings):
        """API key 未配置时抛出 LlmNotConfiguredError。"""
        mock_settings.ai_api_key = ""
        mock_settings.ai_model = "test-model"
        mock_settings.ai_base_url = "http://test"

        # Reset singleton
        import app.core.llm as llm_module
        llm_module.LLM_INSTANCE = None

        with pytest.raises(LlmNotConfiguredError) as exc_info:
            from app.core.llm import get_llm
            get_llm()

        assert "AI API key 未配置" in str(exc_info.value)

    @patch("app.core.llm.ChatOpenAI")
    @patch("app.core.llm.settings")
    def test_get_llm_returns_chat_openai_instance(self, mock_settings, mock_chat_openai: MagicMock) -> None:
        """验证 get_llm 返回 ChatOpenAI 实例。"""
        mock_settings.ai_api_key = "test-key"
        mock_settings.ai_model = "qwen3.5-plus-2026-04-20"
        mock_settings.ai_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        # Reset singleton to force re-creation
        import app.core.llm as llm_module
        llm_module.LLM_INSTANCE = None

        from app.core.llm import get_llm
        llm = get_llm()

        assert llm is mock_instance
        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args.kwargs
        assert call_kwargs["model"] == "qwen3.5-plus-2026-04-20"
        assert call_kwargs["api_key"] == "test-key"
        assert call_kwargs["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"


class TestEnableThinking:
    """测试 enable_thinking 配置不再传递给 API。"""

    @patch("app.core.llm.ChatOpenAI")
    @patch("app.core.llm.settings")
    def test_no_model_kwargs_passed(self, mock_settings, mock_chat_openai: MagicMock) -> None:
        """enable_thinking 不再通过 model_kwargs 传递给 API。"""
        mock_settings.ai_api_key = "test-key"
        mock_settings.ai_model = "qwen3.6-flash"
        mock_settings.ai_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        mock_settings.ai = MagicMock()
        mock_settings.ai.enable_thinking = False

        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        import app.core.llm as llm_module
        llm_module.LLM_INSTANCE = None

        from app.core.llm import get_llm
        get_llm()

        call_kwargs = mock_chat_openai.call_args.kwargs
        assert "model_kwargs" not in call_kwargs
