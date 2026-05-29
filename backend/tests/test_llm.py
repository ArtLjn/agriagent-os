from unittest.mock import MagicMock, patch

import pytest

from app.agent.llm import LlmNotConfiguredError


def _make_fallback_manager():
    """创建一个 fallback_mode=True 的 mock Manager。"""
    manager = MagicMock()
    manager.fallback_mode = True
    return manager


def _reset_llm_singletons():
    """重置 llm.py 和 llm_client_manager.py 的单例。"""
    import app.agent.llm as llm_module
    import app.core.llm_client_manager as mgr_module

    llm_module.LLM_INSTANCE = None
    mgr_module._manager = None


class TestGetLlm:
    """测试 LLM 客户端工厂。"""

    @patch("app.core.llm_client_manager.get_llm_manager")
    @patch("app.agent.llm.settings")
    def test_get_llm_raises_when_api_key_empty(self, mock_settings, mock_get_manager):
        """API key 未配置且 Manager fallback 时抛出 LlmNotConfiguredError。"""
        mock_settings.ai_api_key = ""
        mock_settings.ai_model = "test-model"
        mock_settings.ai_base_url = "http://test"
        mock_get_manager.return_value = _make_fallback_manager()

        _reset_llm_singletons()

        with pytest.raises(LlmNotConfiguredError) as exc_info:
            from app.agent.llm import get_llm

            get_llm()

        assert "AI API key 未配置" in str(exc_info.value)

    @patch("app.agent.llm.ChatOpenAI")
    @patch("app.core.llm_client_manager.get_llm_manager")
    @patch("app.agent.llm.settings")
    def test_get_llm_returns_chat_openai_instance(
        self, mock_settings, mock_get_manager, mock_chat_openai: MagicMock
    ) -> None:
        """验证 get_llm 在 Manager fallback 时返回 config.yaml 的 ChatOpenAI 实例。"""
        mock_settings.ai_api_key = "test-key"
        mock_settings.ai_model = "qwen3.5-plus-2026-04-20"
        mock_settings.ai_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        mock_settings.circuit_breaker_config = MagicMock(
            retry_max=1, retry_backoff_base=1
        )
        mock_settings.ai = MagicMock(enable_thinking=True)
        mock_get_manager.return_value = _make_fallback_manager()

        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        _reset_llm_singletons()

        from app.agent.llm import get_llm

        llm = get_llm()

        assert llm is mock_instance
        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args.kwargs
        assert call_kwargs["model"] == "qwen3.5-plus-2026-04-20"
        assert call_kwargs["api_key"] == "test-key"
        assert (
            call_kwargs["base_url"]
            == "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )

    @patch("app.core.llm_client_manager.get_llm_manager")
    @patch("app.agent.llm.settings")
    def test_get_llm_uses_manager_when_available(self, mock_settings, mock_get_manager):
        """验证 get_llm 优先使用 Manager 而非 config.yaml。"""
        mock_settings.circuit_breaker_config = MagicMock(
            retry_max=1, retry_backoff_base=1
        )
        mock_settings.ai = MagicMock(enable_thinking=True)

        mock_manager = MagicMock()
        mock_manager.fallback_mode = False
        mock_manager.get_model_info.return_value = {
            "provider": "ollama",
            "model": "gemma3:12b",
            "base_url": "https://ollama.com/v1",
        }
        mock_llm = MagicMock()
        mock_manager.get_chat_model.return_value = mock_llm
        mock_get_manager.return_value = mock_manager

        _reset_llm_singletons()

        from app.agent.llm import get_llm

        llm = get_llm()

        assert llm is mock_llm
        mock_manager.get_chat_model.assert_called_once()


class TestEnableThinking:
    """测试 enable_thinking 配置不再传递给 API。"""

    @patch("app.agent.llm.ChatOpenAI")
    @patch("app.core.llm_client_manager.get_llm_manager")
    @patch("app.agent.llm.settings")
    def test_no_model_kwargs_passed(
        self, mock_settings, mock_get_manager, mock_chat_openai: MagicMock
    ) -> None:
        """enable_thinking 不再通过 model_kwargs 传递给 API。"""
        mock_settings.ai_api_key = "test-key"
        mock_settings.ai_model = "qwen3.6-flash"
        mock_settings.ai_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        mock_settings.circuit_breaker_config = MagicMock(
            retry_max=1, retry_backoff_base=1
        )
        mock_settings.ai = MagicMock()
        mock_settings.ai.enable_thinking = False
        mock_get_manager.return_value = _make_fallback_manager()

        mock_instance = MagicMock()
        mock_chat_openai.return_value = mock_instance

        _reset_llm_singletons()

        from app.agent.llm import get_llm

        get_llm()

        call_kwargs = mock_chat_openai.call_args.kwargs
        assert "model_kwargs" not in call_kwargs
