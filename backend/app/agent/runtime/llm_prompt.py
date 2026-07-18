"""Agent Runtime LLM system prompt 渲染。"""

from app.agent.router import RouterDecision
from app.agent.runtime.chat_fallbacks import (
    SYSTEM_BASE_SCENE,
    select_system_prompt_scene,
)
from app.agent.runtime.llm_support import (
    _get_farm_context,
    _get_runtime_context_bundle,
    _get_season,
)
from app.context.models import ContextBundle
from app.shared.time import get_request_date
from app.prompt.cache import get_prompt_cache  # harness-exempt: 迁移期 prompt fallback
from app.prompt.composer import get_composer  # harness-exempt: 迁移期 prompt fallback


async def _prepare_context_bundle(
    *,
    prepared_context_bundle,
    farm_id: int,
    intent: str,
    selected_tool_names: list[str],
    router_decision: RouterDecision,
    user_id: int | None,
    session_id: str | None,
):
    """准备 runtime context bundle 和 farm context。"""
    if prepared_context_bundle is not None:
        if not isinstance(prepared_context_bundle, ContextBundle):
            raise TypeError("prepared context_bundle must be ContextBundle")
        context_bundle = prepared_context_bundle
        farm_ctx = await _get_farm_context(farm_id)
    else:
        context_bundle, farm_ctx = await _get_runtime_context_bundle(
            farm_id=farm_id,
            intent=intent,
            selected_tool_names=selected_tool_names,
            context_dependencies=router_decision.context_dependencies,
            user_id=user_id,
            session_id=session_id,
        )
    if not context_bundle.blocks and farm_ctx.get("display_name") == "农友":
        farm_ctx = await _get_farm_context(farm_id)
    return context_bundle, farm_ctx


def _compose_system_text(
    *,
    prepared_system_prompt: str | None,
    farm_id: int,
    farm_ctx: dict,
    selected_tool_names: list[str],
    has_tool_results: bool,
    router_decision: RouterDecision,
) -> tuple[str, str]:
    """渲染 system prompt，保持原有缓存 key 与 scene 选择。"""
    if prepared_system_prompt:
        return prepared_system_prompt, "prepared"

    current_date = get_request_date()
    prompt_scene = select_system_prompt_scene(
        selected_tool_names=selected_tool_names,
        has_tool_results=has_tool_results,
        router_decision=router_decision,
    )
    prompt_variables = _prompt_variables(farm_ctx, _get_season(current_date))
    if prompt_scene != SYSTEM_BASE_SCENE:
        return (
            get_composer().compose(
                prompt_scene,
                variables=prompt_variables,
                current_date=current_date,
            ),
            prompt_scene,
        )
    return _compose_cached_base_prompt(
        farm_id=farm_id,
        current_date=current_date,
        assistant_role=prompt_variables["assistant_role"],
        prompt_variables=prompt_variables,
    )


def _prompt_variables(farm_ctx: dict, current_season: str) -> dict:
    assistant_role = farm_ctx.get("assistant_role", "warm")
    return {
        "display_name": farm_ctx["display_name"],
        "farm_location": farm_ctx["farm_location"],
        "farm_coords": farm_ctx["farm_coords"],
        "current_season": current_season,
        "active_crops": farm_ctx["active_crops"],
        "assistant_role": assistant_role,
        "assistant_role_prompt": farm_ctx.get("assistant_role_prompt", ""),
    }


def _compose_cached_base_prompt(
    *,
    farm_id: int,
    current_date,
    assistant_role: str,
    prompt_variables: dict,
) -> tuple[str, str]:
    prompt_cache = get_prompt_cache()
    cache_date_key = f"{current_date}:{assistant_role}"
    cached_prompt = prompt_cache.get(farm_id=farm_id, date_str=cache_date_key)
    if cached_prompt is not None:
        return cached_prompt, SYSTEM_BASE_SCENE
    system_text = get_composer().compose(
        SYSTEM_BASE_SCENE,
        variables=prompt_variables,
        current_date=current_date,
    )
    prompt_cache.set(farm_id=farm_id, date_str=cache_date_key, value=system_text)
    return system_text, SYSTEM_BASE_SCENE


__all__ = ["_compose_system_text", "_prepare_context_bundle"]
