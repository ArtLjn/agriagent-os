"""写操作确认机制 — pending action 存储与意图检测。"""

import logging
import re
import time
import uuid
from dataclasses import dataclass

from langchain_core.messages import ToolMessage

_CONFIRM_PATTERNS = re.compile(r"(确认|好的|是的|没问题|对)")
_CANCEL_PATTERNS = re.compile(r"(算了|取消|不要了|不需要了)")

WRITE_SKILLS = frozenset(
    {
        "create_cost_record",
        "create_crop_cycle",
        "create_crop_template",
        "log_farm_activity",
        "settle_debt",
        "update_crop_stage",
    }
)

# 写操作 skill -> 需要失效的 skill 缓存组
_CACHE_INVALIDATION_MAP: dict[str, list[str]] = {
    "create_cost_record": ["cost_analytics", "cost_summary", "get_farm_status"],
    "create_crop_cycle": ["crop_cycle", "get_farm_status"],
    "create_crop_template": [],
    "log_farm_activity": ["farm_logs", "get_farm_status"],
    "settle_debt": ["cost_analytics", "cost_summary", "get_farm_status"],
    "update_crop_stage": ["crop_cycle", "get_farm_status"],
}


def get_cache_groups_for_skill(skill_name: str) -> list[str]:
    """返回写操作 skill 执行后需要清除的 skill 缓存组。"""
    return _CACHE_INVALIDATION_MAP.get(skill_name, [])


_SKILL_DISPLAY: dict[str, str] = {
    "create_cost_record": "记账",
    "create_crop_cycle": "创建茬口",
    "create_crop_template": "创建作物模板",
    "log_farm_activity": "记录农事",
    "settle_debt": "还款",
    "update_crop_stage": "更新阶段",
}

_SKILL_EMOJI: dict[str, str] = {
    "create_cost_record": "💰",
    "create_crop_cycle": "🌱",
    "create_crop_template": "📋",
    "log_farm_activity": "📝",
    "settle_debt": "💳",
    "update_crop_stage": "🔄",
}

_SKILL_PARAM_FORMAT: dict[str, list[str]] = {
    "create_cost_record": ["category", "amount", "record_type"],
    "create_crop_cycle": ["crop_name", "season"],
    "create_crop_template": ["crop_name"],
    "log_farm_activity": ["operation_type"],
    "settle_debt": ["counterparty", "amount"],
    "update_crop_stage": ["stage_name"],
}

_TIMEOUT_SECONDS = 300  # 5分钟超时

logger = logging.getLogger(__name__)


@dataclass
class PendingAction:
    """待确认的操作。"""

    action_id: str
    skill_name: str
    params: dict
    created_at: float
    farm_id: int
    original_input: str = ""
    follow_up_skill_name: str | None = None
    follow_up_params: dict | None = None
    follow_up_original_input: str = ""


# 内存字典：farm_id -> PendingAction
_pending: dict[int, PendingAction] = {}


def store_pending(
    farm_id: int,
    skill_name: str,
    params: dict,
    original_input: str = "",
    follow_up_skill_name: str | None = None,
    follow_up_params: dict | None = None,
    follow_up_original_input: str = "",
) -> str:
    """存储 pending action，返回 action_id。"""
    action_id = uuid.uuid4().hex
    _pending[farm_id] = PendingAction(
        action_id=action_id,
        skill_name=skill_name,
        params=params,
        created_at=time.time(),
        farm_id=farm_id,
        original_input=original_input,
        follow_up_skill_name=follow_up_skill_name,
        follow_up_params=follow_up_params,
        follow_up_original_input=follow_up_original_input,
    )
    logger.info(
        "Pending action 已存储 | farm_id=%d | action_id=%s | skill=%s",
        farm_id,
        action_id,
        skill_name,
    )
    return action_id


def get_pending(farm_id: int) -> PendingAction | None:
    """获取 pending action，超时则删除返回 None。"""
    action = _pending.get(farm_id)
    if action is None:
        return None
    if time.time() - action.created_at > _TIMEOUT_SECONDS:
        logger.warning(
            "Pending action 已超时 | farm_id=%d | skill=%s",
            farm_id,
            action.skill_name,
        )
        del _pending[farm_id]
        return None
    logger.debug(
        "Pending action 获取 | farm_id=%d | skill=%s",
        farm_id,
        action.skill_name,
    )
    return action


def remove_pending(farm_id: int) -> None:
    """删除 pending action。"""
    _pending.pop(farm_id, None)
    logger.debug("Pending action 已删除 | farm_id=%d", farm_id)


def is_write_skill(skill_name: str) -> bool:
    """判断是否为写操作 Skill。"""
    return skill_name in WRITE_SKILLS


PENDING_MARKER = "[PENDING_ACTION]"


def build_confirm_message(
    skill_name: str, params: dict, original_input: str = ""
) -> str:
    emoji = _SKILL_EMOJI.get(skill_name, "❓")
    action = _SKILL_DISPLAY.get(skill_name, skill_name)

    param_keys = _SKILL_PARAM_FORMAT.get(skill_name, list(params.keys()))
    parts = []
    for k in param_keys:
        v = params.get(k)
        if v is not None:
            if k == "amount":
                parts.append(f"{v}元")
            elif k == "record_type":
                label = "收入" if v == "income" else "支出"
                parts.append(label)
            else:
                parts.append(str(v))

    detail = " ".join(parts) if parts else ""

    lines = []
    lines.append(f"{emoji} 确认{action}：{detail}")

    if original_input:
        lines.append(f"理解：您说的是「{original_input}」")

    lines.append("确认吗？")
    return "\n".join(lines)


def is_pending_tool_message(message) -> bool:
    return isinstance(message, ToolMessage) and PENDING_MARKER in (
        message.content or ""
    )


def detect_user_intent(message: str) -> str:
    """检测用户消息意图：confirm / cancel / modify。

    只有消息整体较短且以确认词/取消词为主导时才判定为确认/取消，
    避免把"是赊账"误判为确认。
    """
    stripped = message.strip()
    if _CANCEL_PATTERNS.search(stripped):
        result = "cancel"
        logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
        return result

    if _CONFIRM_PATTERNS.search(stripped):
        # 确认词匹配后，检查消息长度。短消息（<=10字）才判定为确认，
        # 长消息更可能是修正参数
        confirm_match = _CONFIRM_PATTERNS.search(stripped)
        match_end = confirm_match.end()
        # 确认词后还有较多内容时，视为修正
        remaining = stripped[match_end:].strip()
        if len(stripped) <= 10 and not remaining:
            result = "confirm"
            logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
            return result
        # 如果整条消息就是确认词（如"确认"、"好的"）
        if stripped == confirm_match.group(0):
            result = "confirm"
            logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
            return result
        # 确认词开头且后面内容很短（如"确认一下"、"好的，就这样"）
        if len(remaining) <= 4 and not any(c.isdigit() for c in remaining):
            result = "confirm"
            logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
            return result

    result = "modify"
    logger.debug("意图检测 | message=%s | intent=%s", message[:20], result)
    return result


__all__ = [
    "PendingAction",
    "store_pending",
    "get_pending",
    "remove_pending",
    "is_write_skill",
    "detect_user_intent",
    "build_confirm_message",
    "is_pending_tool_message",
    "PENDING_MARKER",
    "_pending",
    "WRITE_SKILLS",
    "get_cache_groups_for_skill",
]
