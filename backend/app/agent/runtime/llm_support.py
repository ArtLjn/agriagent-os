"""Agent Runtime LLM 支撑与上下文辅助。"""

import asyncio
import importlib
import logging
import threading
from datetime import date

from app.agent.prompt_cache import get_farm_ctx_cache
from app.agent.tool_selector import LLMIntentClassifier
from app.context.models import ContextBundle
from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

_LLM_SEMAPHORE = asyncio.Semaphore(5)

_classifier: LLMIntentClassifier | None = None
_classifier_lock = threading.Lock()


def _get_classifier() -> LLMIntentClassifier | None:
    global _classifier
    if _classifier is not None:
        return _classifier

    api_key = settings.ai_api_key
    base_url = settings.ai_base_url
    model = settings.ai_model

    # 优先从 Manager 获取轻量模型（tool-selection 角色）
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            client, info = manager.get_sync_client_with_info(role="tool-selection")
            api_key = client.api_key
            base_url = client.base_url
            model = info["model"]
            provider = str(info["provider"])
            logger.info(
                "tool_select 模型选择 | provider=%s | model=%s | role=%s | base_url=%s",
                provider,
                model,
                info["role"],
                info["base_url"],
            )
        else:
            provider = "config.yaml"
    except Exception as e:
        logger.debug("从 Manager 获取 classifier 参数失败 | error=%s", e)
        provider = "config.yaml"

    if api_key:
        with _classifier_lock:
            if _classifier is None:
                _classifier = LLMIntentClassifier(
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    provider=provider,
                    role="tool-selection",
                )
    return _classifier


def _get_season(current_date: date | None = None) -> str:
    """根据当前月份返回季节。"""
    if current_date is None:
        current_date = date.today()
    month = current_date.month
    if month in (3, 4, 5):
        return "春季"
    elif month in (6, 7, 8):
        return "夏季"
    elif month in (9, 10, 11):
        return "秋季"
    else:
        return "冬季"


def _build_circuit_key(llm_instance) -> str:
    """从 LLM 实例构建 cooldown key（provider_name/model_id）。"""
    model_id = getattr(llm_instance, "model_name", "") or getattr(
        llm_instance, "model", ""
    )
    base_url = ""
    try:
        base_url = getattr(llm_instance, "base_url", "") or llm_instance.openai_api_base
    except Exception:
        pass

    # 从 Manager chain 中匹配 provider name
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            for provider, model in manager.chain:
                if model.id == model_id and base_url and provider.base_url in base_url:
                    return f"{provider.name}/{model.id}"
    except Exception:
        pass
    return model_id or "unknown"


def _record_llm_failure(circuit_key: str, exc: Exception) -> None:
    """LLM 调用失败，记录到 Manager cooldown。"""
    try:
        from app.core.llm_client_manager import get_llm_manager, classify_error

        manager = get_llm_manager()
        if not manager.fallback_mode:
            level = classify_error(exc)
            manager.record_failure(circuit_key, error_level=level)
            logger.warning(
                "LLM 故障记录 | key=%s | level=%s | error=%s",
                circuit_key,
                level.value,
                str(exc)[:120],
            )
    except Exception as e:
        logger.debug("记录 LLM 故障失败 | error=%s", e)


def _record_llm_success(circuit_key: str) -> None:
    """LLM 调用成功，清除 cooldown。"""
    try:
        from app.core.llm_client_manager import get_llm_manager

        manager = get_llm_manager()
        if not manager.fallback_mode:
            manager.record_success(circuit_key)
    except Exception:
        pass


async def _get_farm_context(farm_id: int) -> dict:
    """异步获取农场上下文（位置、坐标、称呼、种植信息），带 5 分钟 TTL 缓存。"""
    cache = get_farm_ctx_cache()
    cached = cache.get(farm_id)
    if cached is not None:
        return cached

    def _query() -> dict:
        db = SessionLocal()
        try:
            context_builder_module = importlib.import_module(
                ".".join(["app", "context", "builder"])
            )
            context_builder = context_builder_module.ContextBuilder(max_tokens=256)

            return context_builder.build_farm_runtime_context(
                db=db,
                farm_id=farm_id,
            )
        except Exception:
            logger.warning("获取农场上下文失败，使用默认值", exc_info=True)
            return {
                "farm_location": "",
                "farm_coords": "",
                "display_name": "农友",
                "active_crops": "",
            }
        finally:
            db.close()

    result = await asyncio.to_thread(_query)
    cache.set(farm_id, result)
    return result


async def _get_runtime_context_bundle(
    farm_id: int,
    intent: str,
    selected_tool_names: list[str],
    context_dependencies: list[str] | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    memory_context_loader=None,
) -> tuple[ContextBundle, dict]:
    """构建 Runtime ContextBundle，并返回兼容旧 prompt 的 farm context。"""

    def _query() -> tuple[ContextBundle, dict]:
        db = SessionLocal()
        try:
            from app.context.builder import ContextBuilder
            from app.context.policy import ContextBuildRequest

            memory_context = None
            if user_id:
                loader = memory_context_loader
                if loader is None:
                    from app.agent.application.context_memory import load_memory_context

                    loader = load_memory_context
                memory_context = asyncio.run(
                    loader(
                        user_id=user_id,
                        farm_id=farm_id,
                        session_id=session_id,
                    )
                )

            context_builder = ContextBuilder()
            request = ContextBuildRequest(
                intent=intent,
                selected_tool_names=list(selected_tool_names),
                context_dependencies=list(context_dependencies or []),
                farm_id=farm_id,
                user_id=user_id,
                session_id=session_id,
            )
            bundle = context_builder.build_runtime_context_bundle(
                db=db,
                request=request,
                memory_context=memory_context,
            )
            farm_ctx = context_builder.build_farm_runtime_context(
                db=db,
                farm_id=farm_id,
            )
            return bundle, farm_ctx
        finally:
            db.close()

    try:
        return await asyncio.to_thread(_query)
    except Exception:
        logger.warning("构建 Runtime ContextBundle 失败，使用降级上下文", exc_info=True)
        farm_ctx = await _get_farm_context(farm_id)
        return (
            ContextBundle(
                blocks=[],
                token_budget=0,
                token_estimate=0,
                metadata={"fallback": True},
            ),
            farm_ctx,
        )


async def _warm_tool_caches(
    selected_names: list[str],
    farm_id: int,
    farm_ctx: dict,
    context_dependencies: list[str] | None = None,
) -> None:
    """并行预热已选 tool 的底层缓存，2s 超时，失败不影响主流程。"""
    preload_module = importlib.import_module(".".join(["app", "context", "preload"]))

    await preload_module.warm_tool_caches(
        selected_names,
        farm_id,
        farm_ctx,
        context_dependencies=context_dependencies,
    )


__all__ = [
    "_LLM_SEMAPHORE",
    "_build_circuit_key",
    "_get_classifier",
    "_get_farm_context",
    "_get_runtime_context_bundle",
    "_get_season",
    "_record_llm_failure",
    "_record_llm_success",
    "_warm_tool_caches",
]
