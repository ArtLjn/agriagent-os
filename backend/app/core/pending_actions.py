"""写操作确认机制 — pending action 存储与意图检测。"""

import re
import time
import uuid
from dataclasses import dataclass

_CONFIRM_PATTERNS = re.compile(r"(确认|好的|是的|没问题|对)")
_CANCEL_PATTERNS = re.compile(r"(算了|取消|不要了|不需要了)")

WRITE_SKILLS = frozenset(
    {
        "create_cost_record",
        "create_crop_cycle",
        "log_farm_activity",
        "settle_debt",
        "update_crop_stage",
    }
)

_TIMEOUT_SECONDS = 300  # 5分钟超时


@dataclass
class PendingAction:
    """待确认的操作。"""

    action_id: str
    skill_name: str
    params: dict
    created_at: float
    farm_id: int


# 内存字典：farm_id -> PendingAction
_pending: dict[int, PendingAction] = {}


def store_pending(farm_id: int, skill_name: str, params: dict) -> str:
    """存储 pending action，返回 action_id。"""
    action_id = uuid.uuid4().hex
    _pending[farm_id] = PendingAction(
        action_id=action_id,
        skill_name=skill_name,
        params=params,
        created_at=time.time(),
        farm_id=farm_id,
    )
    return action_id


def get_pending(farm_id: int) -> PendingAction | None:
    """获取 pending action，超时则删除返回 None。"""
    action = _pending.get(farm_id)
    if action is None:
        return None
    if time.time() - action.created_at > _TIMEOUT_SECONDS:
        del _pending[farm_id]
        return None
    return action


def remove_pending(farm_id: int) -> None:
    """删除 pending action。"""
    _pending.pop(farm_id, None)


def is_write_skill(skill_name: str) -> bool:
    """判断是否为写操作 Skill。"""
    return skill_name in WRITE_SKILLS


def detect_user_intent(message: str) -> str:
    """检测用户消息意图：confirm / cancel / modify。

    只有消息整体较短且以确认词/取消词为主导时才判定为确认/取消，
    避免把"是赊账"误判为确认。
    """
    stripped = message.strip()
    if _CANCEL_PATTERNS.search(stripped):
        # 如果消息包含取消词，判定为取消
        return "cancel"

    if _CONFIRM_PATTERNS.search(stripped):
        # 确认词匹配后，检查消息长度。短消息（<=10字）才判定为确认，
        # 长消息更可能是修正参数
        confirm_match = _CONFIRM_PATTERNS.search(stripped)
        match_end = confirm_match.end()
        # 确认词后还有较多内容时，视为修正
        remaining = stripped[match_end:].strip()
        if len(stripped) <= 10 and not remaining:
            return "confirm"
        # 如果整条消息就是确认词（如"确认"、"好的"）
        if stripped == confirm_match.group(0):
            return "confirm"
        # 确认词开头且后面内容很短（如"确认一下"、"好的，就这样"）
        if len(remaining) <= 4 and not any(c.isdigit() for c in remaining):
            return "confirm"

    return "modify"


__all__ = [
    "PendingAction",
    "store_pending",
    "get_pending",
    "remove_pending",
    "is_write_skill",
    "detect_user_intent",
    "_pending",
    "WRITE_SKILLS",
]
