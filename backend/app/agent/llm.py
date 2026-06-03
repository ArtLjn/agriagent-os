"""LLM 客户端封装，使用 LangChain ChatOpenAI。"""

import logging

import langchain

for _attr in ("verbose", "debug", "llm_cache"):
    if not hasattr(langchain, _attr):
        setattr(langchain, _attr, False)

from langchain_core.language_models.chat_models import BaseChatModel  # noqa: E402
from langchain_openai import ChatOpenAI  # noqa: E402

from app.core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)


class LlmNotConfiguredError(Exception):
    """LLM 未配置错误。"""

    pass


def get_llm(*, role: str = "generation") -> BaseChatModel:
    """获取 LLM 实例（每次返回新实例以支持负载均衡）。"""
    cb = settings.circuit_breaker_config
    extra_body: dict = {}
    if not settings.ai.enable_thinking:
        extra_body["enable_thinking"] = False

    # 优先从 LLMClientManager 获取
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            llm, info = manager.get_chat_model_with_info(
                role=role,
                temperature=0.7,
                max_retries=cb.retry_max,
                timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
                extra_body=extra_body if extra_body else None,
            )
            logger.info(
                (
                    "LLM 请求模型选择 | provider=%s | model=%s | role=%s | "
                    "api_key_slot=%s/%s | circuit_key=%s | base_url=%s"
                ),
                info["provider"],
                info["model"],
                info["role"],
                int(info["api_key_index"]) + 1,
                info["api_key_count"],
                info["circuit_key"],
                info["base_url"],
            )
            return llm
    except Exception as e:
        logger.warning("LLMClientManager 失败，回退 config.yaml | error=%s", e)

    # 兜底: config.yaml
    if not settings.ai_api_key:
        raise LlmNotConfiguredError(
            "AI API key 未配置。请在 providers.json 或 config.yaml 中设置。"
        )

    llm = ChatOpenAI(
        model=settings.ai_model,
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        temperature=0.7,
        streaming=True,
        max_retries=cb.retry_max,
        timeout=cb.retry_backoff_base * (2**cb.retry_max) * 2,
        extra_body=extra_body if extra_body else None,
    )
    logger.info(
        "LLM 请求模型选择 | provider=config.yaml | model=%s | role=%s | base_url=%s",
        settings.ai_model,
        role,
        settings.ai_base_url,
    )
    return llm


__all__ = ["get_llm"]
