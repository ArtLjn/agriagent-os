"""LLM 客户端封装，使用 LangChain ChatOpenAI 接入 DashScope。"""

import logging

import langchain

for _attr in ("verbose", "debug", "llm_cache"):
    if not hasattr(langchain, _attr):
        setattr(langchain, _attr, False)

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from app.core.circuit_breaker import CircuitBreaker, call_with_retry  # noqa: E402
from app.core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

LLM_INSTANCE: ChatOpenAI | None = None
_BREAKER: CircuitBreaker | None = None


class LlmNotConfiguredError(Exception):
    """LLM 未配置错误。"""

    pass


def _get_breaker() -> CircuitBreaker:
    global _BREAKER
    if _BREAKER is None:
        cb = settings.circuit_breaker_config
        _BREAKER = CircuitBreaker(
            failure_threshold=cb.failure_threshold,
            recovery_timeout=cb.recovery_timeout,
        )
    return _BREAKER


def get_llm() -> BaseChatModel:
    """获取全局 LLM 实例（带熔断保护）。"""
    global LLM_INSTANCE
    if LLM_INSTANCE is None:
        if not settings.ai_api_key:
            raise LlmNotConfiguredError(
                "AI API key 未配置。请在 config.yaml 中设置 ai.api_key，"
                "或设置 AI_API_KEY 环境变量。"
            )
        cb = settings.circuit_breaker_config
        model_kwargs = {}
        if hasattr(settings, "ai") and hasattr(settings.ai, "enable_thinking"):
            model_kwargs["enable_thinking"] = settings.ai.enable_thinking
        LLM_INSTANCE = ChatOpenAI(
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            temperature=0.7,
            max_retries=cb.retry_max,
            timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
            model_kwargs=model_kwargs,
        )
    return LLM_INSTANCE


async def llm_invoke_with_breaker(llm: BaseChatModel, messages: list) -> object:
    """带熔断保护的 LLM 调用。"""
    cb = settings.circuit_breaker_config
    breaker = _get_breaker()
    return await call_with_retry(
        fn=lambda: llm.ainvoke(messages),
        breaker=breaker,
        retry_max=cb.retry_max,
        retry_backoff_base=cb.retry_backoff_base,
    )


__all__ = ["get_llm", "llm_invoke_with_breaker"]
