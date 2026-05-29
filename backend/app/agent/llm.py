"""LLM 客户端封装，使用 LangChain ChatOpenAI 接入 DashScope。"""

import logging

import langchain

for _attr in ("verbose", "debug", "llm_cache"):
    if not hasattr(langchain, _attr):
        setattr(langchain, _attr, False)

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from app.infra.circuit_breaker import CircuitBreaker, call_with_retry  # noqa: E402
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
    """获取全局 LLM 实例（优先 Manager，兜底 config.yaml）。"""
    global LLM_INSTANCE
    if LLM_INSTANCE is None:
        cb = settings.circuit_breaker_config
        extra_body: dict = {}
        if not settings.ai.enable_thinking:
            extra_body["enable_thinking"] = False

        # 优先从 LLMClientManager 获取
        try:
            from app.core.llm_client_manager import get_llm_manager

            manager = get_llm_manager()
            if not manager.fallback_mode:
                LLM_INSTANCE = manager.get_chat_model(
                    temperature=0.7,
                    max_retries=cb.retry_max,
                    timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
                    extra_body=extra_body if extra_body else None,
                )
                info = manager.get_model_info()
                logger.info(
                    "LLM 客户端初始化(Manager) | provider=%s | model=%s",
                    info["provider"],
                    info["model"],
                )
                return LLM_INSTANCE
        except Exception as e:
            logger.warning("LLMClientManager 失败，回退 config.yaml | error=%s", e)

        # 兜底: config.yaml
        if not settings.ai_api_key:
            raise LlmNotConfiguredError(
                "AI API key 未配置。请在 providers.json 或 config.yaml 中设置。"
            )

        LLM_INSTANCE = ChatOpenAI(
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            temperature=0.7,
            max_retries=cb.retry_max,
            timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
            extra_body=extra_body if extra_body else None,
        )
        logger.info("LLM 客户端初始化(config.yaml兜底) | model=%s", settings.ai_model)
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
