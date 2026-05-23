"""LLM 客户端封装，使用 LangChain ChatOpenAI 接入 DashScope。"""

from langchain_openai import ChatOpenAI

from app.core.config import settings


LLM_INSTANCE: ChatOpenAI | None = None


def get_llm() -> ChatOpenAI:
    """获取全局 ChatOpenAI 实例（单例模式）。

    Returns:
        配置好的 ChatOpenAI 实例，连接阿里云 DashScope。
    """
    global LLM_INSTANCE
    if LLM_INSTANCE is None:
        LLM_INSTANCE = ChatOpenAI(
            model=settings.ai_model,
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            temperature=0.7,
        )
    return LLM_INSTANCE


__all__ = ["get_llm"]
