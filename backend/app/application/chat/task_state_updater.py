"""聊天轮次结束后的 TaskState 最小写入入口。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.context.task_state_store import AgentTaskStateStore, TaskStateStatus


@dataclass(frozen=True)
class TaskStateTurn:
    """TaskState 写入所需的轮次快照。"""

    farm_id: int
    user_id: str | None
    session_id: str | None
    user_input: str
    assistant_reply: str
    pending_action: object | None = None
    pending_plan: object | None = None
    pending_decision_handled: bool = False


async def update_task_state_after_turn(db: Session, turn: TaskStateTurn) -> None:
    """根据本轮问答保守更新当前 session 最近一个 TaskState。"""
    if not _can_consider_task_state(turn):
        return

    store = AgentTaskStateStore(db)
    active = store.get_active_task(
        farm_id=turn.farm_id,
        user_id=turn.user_id,
        session_id=turn.session_id,
    )
    missing = _extract_missing_information(turn.assistant_reply)
    if active is not None:
        _handle_existing_task(store, turn, active, missing)
        return

    if not _should_start_task(turn, missing):
        return

    store.upsert_active_task(
        farm_id=turn.farm_id,
        user_id=turn.user_id or "",
        session_id=turn.session_id or "",
        task_type=_classify_task_type(turn.user_input, turn.assistant_reply),
        goal=_compact_text(turn.user_input),
        entities=_extract_entities(turn.user_input),
        observations=_initial_observations(turn),
        missing_information=missing,
        next_action=_next_action_for_missing(missing),
        status=TaskStateStatus.WAITING_USER if missing else TaskStateStatus.ACTIVE,
    )


def _handle_existing_task(
    store: AgentTaskStateStore,
    turn: TaskStateTurn,
    active,
    missing: list[str],
) -> None:
    if _is_cancel_turn(turn):
        store.mark_cancelled(
            farm_id=turn.farm_id,
            user_id=turn.user_id or "",
            session_id=turn.session_id or "",
            task_id=active.task_id,
        )
        return

    if _is_side_query(turn.user_input):
        return

    if not missing and _is_completion_turn(turn):
        store.mark_completed(
            farm_id=turn.farm_id,
            user_id=turn.user_id or "",
            session_id=turn.session_id or "",
            task_id=active.task_id,
        )
        return

    _update_existing_task(store, turn, active, missing)


def _can_consider_task_state(turn: TaskStateTurn) -> bool:
    if not turn.user_id or not turn.session_id:
        return False
    if turn.pending_action is not None or turn.pending_plan is not None:
        return False
    if turn.pending_decision_handled:
        return False
    if not _compact_text(turn.user_input) or not _compact_text(turn.assistant_reply):
        return False
    return True


def _update_existing_task(
    store: AgentTaskStateStore,
    turn: TaskStateTurn,
    active,
    missing: list[str],
) -> None:
    observations = _merge_unique(
        list(active.observations_json or []),
        _observations_from_user_update(turn.user_input),
    )
    next_missing = missing or _remaining_missing_after_user_reply(
        list(active.missing_information_json or []),
        turn.user_input,
    )
    status = TaskStateStatus.WAITING_USER if next_missing else TaskStateStatus.ACTIVE
    store.upsert_active_task(
        farm_id=turn.farm_id,
        user_id=turn.user_id or "",
        session_id=turn.session_id or "",
        task_type=active.task_type,
        goal=active.goal,
        entities={
            **dict(active.entities_json or {}),
            **_extract_entities(turn.user_input),
        },
        observations=observations,
        missing_information=next_missing,
        next_action=_next_action_for_missing(next_missing) or "继续处理当前任务",
        status=status,
        expires_at=active.expires_at,
    )


def _should_start_task(turn: TaskStateTurn, missing: list[str]) -> bool:
    if not missing:
        return False
    if _is_side_query(turn.user_input):
        return False
    return _has_task_signal(turn.user_input)


def _extract_missing_information(reply: str) -> list[str]:
    candidates: list[str] = []
    for pattern in (
        r"(?:还需要|需要|请|麻烦你)?补充[:：]?\s*([^。\n；;]+)",
        r"(?:缺少|缺失|还差)[:：]?\s*([^。\n；;]+)",
        r"(?:请告诉我|需要提供)[:：]?\s*([^。\n；;？?]+)",
    ):
        candidates.extend(re.findall(pattern, reply))
    if not candidates and ("？" in reply or "?" in reply):
        question = re.split(r"[。！？!?]\s*", reply.strip())[-2:]
        candidates.extend(item for item in question if "？" in item or "?" in item)

    items: list[str] = []
    for candidate in candidates:
        items.extend(_split_missing_items(candidate))
    return _merge_unique([], items)[:6]


def _split_missing_items(text: str) -> list[str]:
    cleaned = re.sub(r"^(一下|这些|如下|信息|内容)", "", text.strip())
    cleaned = cleaned.strip(" ：:，,。；;？? ")
    if not cleaned:
        return []
    parts = re.split(r"[、,，/；;]|\s+和\s+|\s+以及\s+|\s+及\s+", cleaned)
    return [
        _normalize_missing_item(part) for part in parts if _normalize_missing_item(part)
    ]


def _normalize_missing_item(text: str) -> str:
    item = re.sub(r"^(请|需要|确认|提供|补充)", "", text.strip())
    item = re.sub(r"(吗|呢|是多少|是什么)$", "", item)
    return item.strip(" ：:，,。；;？? ")


def _remaining_missing_after_user_reply(
    missing: list[str], user_input: str
) -> list[str]:
    if not missing:
        return []
    return [
        item
        for item in missing
        if item and not _user_reply_resolves_missing_item(item, user_input)
    ]


def _user_reply_resolves_missing_item(missing_item: str, user_input: str) -> bool:
    text = user_input.strip()
    if missing_item in text:
        return True
    core_word = _missing_core_word(missing_item)
    if core_word and core_word in text:
        return True
    return _input_unit_matches_missing_item(missing_item, text)


def _missing_core_word(missing_item: str) -> str:
    words = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]+", missing_item)
    if not words:
        return missing_item
    text = "".join(words)
    for suffix in ("信息", "情况", "数据", "大小", "多少"):
        text = text.removesuffix(suffix)
    return text


def _input_unit_matches_missing_item(missing_item: str, user_input: str) -> bool:
    unit_patterns = _unit_patterns_for_missing_item(missing_item)
    if not unit_patterns:
        return False
    return any(re.search(pattern, user_input) for pattern in unit_patterns)


def _unit_patterns_for_missing_item(missing_item: str) -> list[str]:
    if any(keyword in missing_item for keyword in ("功率", "瓦数", "补光灯")):
        return [r"\d+(?:\.\d+)?\s*(?:瓦|w|W|千瓦|kw|KW)"]
    if any(keyword in missing_item for keyword in ("面积", "亩数", "棚室")):
        return [r"\d+(?:\.\d+)?\s*(?:亩|平方米|平米|㎡|m2|M2)"]
    if any(keyword in missing_item for keyword in ("重量", "用量", "剂量")):
        return [r"\d+(?:\.\d+)?\s*(?:斤|公斤|千克|克|g|G|kg|KG)"]
    if any(keyword in missing_item for keyword in ("数量", "株数", "棵数")):
        return [r"\d+(?:\.\d+)?\s*(?:株|棵|个|袋|瓶|箱)"]
    if any(keyword in missing_item for keyword in ("金额", "价格", "费用")):
        return [r"\d+(?:\.\d+)?\s*(?:元|块|万元|万)"]
    if any(keyword in missing_item for keyword in ("日期", "时间", "天数", "周期")):
        return [r"\d+(?:\.\d+)?\s*(?:天|小时|日|号)", r"(?:今天|明天|后天|昨天)"]
    return []


def _observations_from_user_update(user_input: str) -> list[str]:
    if _is_greeting(user_input):
        return []
    return [f"用户补充：{_compact_text(user_input)}"]


def _initial_observations(turn: TaskStateTurn) -> list[str]:
    entities = _extract_entities(turn.user_input)
    observations = []
    if entities:
        observations.append("用户已经提供：" + "、".join(entities.values()))
    return observations


def _extract_entities(text: str) -> dict[str, str]:
    crop = _extract_crop(text)
    entities = {}
    if crop:
        entities["crop"] = crop
    greenhouse = re.search(r"([\w一二三四五六七八九十\d号#-]+棚)", text)
    if greenhouse:
        entities["greenhouse"] = greenhouse.group(1)
    return entities


def _extract_crop(text: str) -> str:
    crops = (
        "番茄",
        "黄瓜",
        "西瓜",
        "水稻",
        "玉米",
        "辣椒",
        "茄子",
        "草莓",
        "小麦",
        "大豆",
    )
    for crop in crops:
        if crop in text:
            return crop
    match = re.search(r"给(.{1,8}?)(?:做|制定|出|安排|诊断|补光|施肥|打药)", text)
    return match.group(1).strip() if match else ""


def _classify_task_type(user_input: str, assistant_reply: str) -> str:
    text = user_input + assistant_reply
    if any(keyword in text for keyword in ("诊断", "病害", "虫害", "症状", "叶斑")):
        return "diagnosis_followup"
    if any(keyword in text for keyword in ("计划", "方案", "安排", "建议", "测算")):
        return "plan_draft"
    return "followup_task"


def _next_action_for_missing(missing: list[str]) -> str | None:
    if not missing:
        return None
    return f"等待用户补充：{missing[0]}"


def _has_task_signal(text: str) -> bool:
    return any(
        keyword in text
        for keyword in (
            "帮我",
            "制定",
            "计划",
            "方案",
            "安排",
            "诊断",
            "分析",
            "怎么处理",
            "怎么办",
            "建议",
            "规划",
        )
    )


def _is_completion_turn(turn: TaskStateTurn) -> bool:
    reply = turn.assistant_reply
    return any(
        keyword in reply
        for keyword in (
            "已经整理完成",
            "已整理完成",
            "方案已经",
            "诊断建议已经",
            "已完成",
            "可以按",
        )
    )


def _is_cancel_turn(turn: TaskStateTurn) -> bool:
    text = turn.user_input.strip()
    return any(keyword in text for keyword in ("取消", "不用了", "先不做", "作废"))


def _is_side_query(text: str) -> bool:
    return _is_greeting(text) or _is_accounting_query(text)


def _is_greeting(text: str) -> bool:
    normalized = re.sub(r"\s+", "", text)
    return normalized in {"你好", "您好", "hello", "hi", "嗨", "在吗"}


def _is_accounting_query(text: str) -> bool:
    return any(
        keyword in text
        for keyword in (
            "账",
            "记一笔",
            "记账",
            "收入",
            "支出",
            "花了",
            "买了",
            "卖了",
            "欠款",
            "赊账",
        )
    )


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _merge_unique(base: list[str], additions: list[str]) -> list[str]:
    merged = [item for item in base if item]
    for item in additions:
        if item and item not in merged:
            merged.append(item)
    return merged


__all__ = ["TaskStateTurn", "update_task_state_after_turn"]
