"""Executor 级 pending action 统一服务。"""

import logging
import re
import time

from app.agent.executor.models import PendingActionDecision
from app.agent.skills import get_langchain_tools
from app.infra.pending_actions import (
    PendingAction,
    build_confirm_message,
    detect_user_intent,
    get_cache_groups_for_skill,
    get_pending,
    remove_pending,
    store_pending,
)
from app.infra.skill_cache import clear_cache as clear_skill_cache
from app.infra.trace_collector import get_collector

logger = logging.getLogger(__name__)

_MISSING_TEMPLATE_RE = re.compile(r"系统还没有\s*(?P<crop>.+?)\s*模板")
_CLEAR_CORRECTION_RE = re.compile(
    r"(?:改成|改为|改到|更正|纠正|不是|金额|分类|日期|对象|备注|\d+\s*(?:元|块|万|w|W|千|百))"
)


async def _execute_write_skill(
    farm_id: int,
    skill_name: str,
    params: dict,
    farm_uid: str | None = None,
) -> str:
    """执行 pending action 中存储的写操作 Skill 并记录 trace。"""
    start = time.time()
    error_msg = None
    result_str = ""
    try:
        tool_map = {
            tool.name: tool
            for tool in get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
        }
        tool = tool_map.get(skill_name)
        if tool is None:
            return f"未知工具: {skill_name}"

        result = await tool.ainvoke(params)
        result_str = str(result)
        return result_str
    except Exception as exc:
        error_msg = str(exc)
        raise
    finally:
        get_collector().record(
            node_type="skill_call",
            node_name=skill_name,
            input_data=params,
            output_data=result_str or None,
            start_time=start,
            end_time=time.time(),
            error_message=error_msg,
        )


def _get_metadata_cache_groups(
    skill_name: str,
    farm_id: int,
    farm_uid: str | None = None,
) -> list[str]:
    """从 LangChain tool metadata 读取缓存失效组，缺失时回退旧映射。"""
    try:
        tool_map = {
            tool.name: tool
            for tool in get_langchain_tools(farm_id=farm_id, farm_uid=farm_uid)
        }
        tool = tool_map.get(skill_name)
        metadata = getattr(tool, "skill_metadata", None) if tool else None
        cache_groups = getattr(metadata, "cache_invalidation", None)
        if cache_groups:
            return list(cache_groups)
    except Exception as exc:
        logger.warning(
            "读取 Skill metadata 缓存失效配置失败，使用 fallback | skill=%s error=%s",
            skill_name,
            exc,
        )

    return get_cache_groups_for_skill(skill_name)


def _clear_cache_groups(skill_name: str, cache_groups: list[str]) -> list[str]:
    """清理指定缓存组。"""
    cleared_groups = []
    for group in cache_groups:
        cleared = clear_skill_cache(group)
        cleared_groups.append(group)
        if cleared:
            logger.info(
                "写操作后清除缓存 | skill=%s group=%s cleared=%d",
                skill_name,
                group,
                cleared,
            )
    return cleared_groups


def _format_follow_up_intro(skill_name: str, params: dict) -> str:
    """生成后续确认动作的自然语言引导。"""
    if skill_name == "create_crop_cycle":
        crop_name = str(params.get("crop_name") or "").strip()
        return (
            f"现在可以继续创建{crop_name}茬口。"
            if crop_name
            else "现在可以继续创建茬口。"
        )

    return "下一步需要继续确认。"


def _is_clear_pending_correction(message: str) -> bool:
    """判断用户是否在明确修正待确认参数，需要交给 LLM 重新规划。"""
    return bool(_CLEAR_CORRECTION_RE.search(message.strip()))


def _extract_missing_template_crop(pending: PendingAction, result: str) -> str:
    """从缺模板结果中提取作物名，优先使用 pending 参数。"""
    crop_name = str(pending.params.get("crop_name") or "").strip()
    if crop_name:
        return crop_name

    match = _MISSING_TEMPLATE_RE.search(result)
    return match.group("crop").strip() if match else ""


async def _confirm_pending(
    farm_id: int,
    pending: PendingAction,
    farm_uid: str | None = None,
    session_id: str | None = None,
) -> PendingActionDecision:
    """执行已确认的 pending action，并处理缺模板和链式动作。"""
    result = await _execute_write_skill(
        farm_id=farm_id,
        skill_name=pending.skill_name,
        params=pending.params,
        farm_uid=farm_uid,
    )
    cache_groups = _get_metadata_cache_groups(
        pending.skill_name,
        farm_id=farm_id,
        farm_uid=farm_uid,
    )
    cleared_groups = _clear_cache_groups(pending.skill_name, cache_groups)
    remove_pending(farm_id, session_id=session_id)
    metadata = {"cache_groups_cleared": cleared_groups}

    if (
        pending.skill_name == "create_crop_cycle"
        and "系统还没有" in result
        and "模板" in result
    ):
        crop_name = _extract_missing_template_crop(pending, result)
        if crop_name:
            store_pending(
                farm_id,
                "create_crop_template",
                {"crop_name": crop_name},
                original_input=f"系统还没有{crop_name}作物模板",
                follow_up_skill_name="create_crop_cycle",
                follow_up_params=dict(pending.params),
                follow_up_original_input=pending.original_input,
                session_id=session_id,
            )
            confirm = build_confirm_message(
                "create_crop_template",
                {"crop_name": crop_name},
                original_input=f"系统还没有{crop_name}作物模板",
            )
            reply = (
                f"系统还没有{crop_name}作物模板。创建茬口前需要先创建模板。\n{confirm}"
            )
            return PendingActionDecision.confirmed(reply, metadata=metadata)

    if pending.follow_up_skill_name and pending.follow_up_params is not None:
        store_pending(
            farm_id,
            pending.follow_up_skill_name,
            dict(pending.follow_up_params),
            original_input=pending.follow_up_original_input,
            session_id=session_id,
        )
        confirm = build_confirm_message(
            pending.follow_up_skill_name,
            pending.follow_up_params,
            original_input=pending.follow_up_original_input,
        )
        intro = _format_follow_up_intro(
            pending.follow_up_skill_name,
            pending.follow_up_params,
        )
        reply = f"已执行：{result}\n\n{intro}\n{confirm}"
        return PendingActionDecision.confirmed(reply, metadata=metadata)

    return PendingActionDecision.confirmed(
        f"已执行：{result}",
        metadata=metadata,
    )


async def handle_pending_action(
    *,
    farm_id: int,
    message: str,
    farm_uid: str | None = None,
    session_id: str | None = None,
) -> PendingActionDecision:
    """根据用户消息处理当前农场的 pending action。"""
    pending = get_pending(farm_id, session_id=session_id)
    if pending is None:
        return PendingActionDecision.unhandled()

    try:
        intent = detect_user_intent(message)
        if intent == "confirm":
            logger.info(
                "用户确认执行 | farm=%s skill=%s params=%s",
                farm_id,
                pending.skill_name,
                pending.params,
            )
            return await _confirm_pending(
                farm_id,
                pending,
                farm_uid=farm_uid,
                session_id=session_id,
            )

        if intent == "cancel":
            remove_pending(farm_id, session_id=session_id)
            return PendingActionDecision.canceled()

        if _is_clear_pending_correction(message):
            return PendingActionDecision.modified()

        confirm = build_confirm_message(
            pending.skill_name,
            pending.params,
            original_input=pending.original_input,
        )
        reply = f"当前有一条待确认操作，还没有执行。\n{confirm}"
        return PendingActionDecision.modified(reply=reply, handled=True)
    except Exception as exc:
        logger.exception("执行 pending action 失败")
        remove_pending(farm_id, session_id=session_id)
        return PendingActionDecision.failed(f"执行失败：{exc}")


__all__ = ["handle_pending_action"]
