"""LLM 客户端封装，使用 LangChain ChatOpenAI 接入 DashScope。"""

import langchain

if not hasattr(langchain, "verbose"):
    langchain.verbose = False

from langchain_openai import ChatOpenAI

from app.core.config import settings


LLM_INSTANCE: ChatOpenAI | None = None


class LlmNotConfiguredError(Exception):
    """LLM 未配置错误。"""

    pass


def get_llm() -> ChatOpenAI:
    """获取全局 ChatOpenAI 实例（单例模式）。

    Returns:
        配置好的 ChatOpenAI 实例，连接阿里云 DashScope。

    Raises:
        LlmNotConfiguredError: AI API key 未配置。
    """
    global LLM_INSTANCE
    if LLM_INSTANCE is None:
        if not settings.ai_api_key:
            raise LlmNotConfiguredError(
                "AI API key 未配置。请在 config.yaml 中设置 ai.api_key，"
                "或设置 AI_API_KEY 环境变量。"
            )
        LLM_INSTANCE = ChatOpenAI(
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            temperature=0.7,
        )
    return LLM_INSTANCE


__all__ = ["get_llm"]
