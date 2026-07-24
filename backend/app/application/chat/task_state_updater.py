"""聊天轮次结束后的 TaskState 最小写入入口。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

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


@dataclass(frozen=True)
class TaskStateUpdateResult:
    """TaskState 收尾决策结果，用于后续 trace 观测。"""

    action: str
    reason: str = ""
    task_id: str | None = None
    task_type: str = ""
    missing_information: list[str] = field(default_factory=list)


async def update_task_state_after_turn(
    db: Session, turn: TaskStateTurn
) -> TaskStateUpdateResult:
    """根据本轮问答保守更新当前 session 最近一个 TaskState。"""
    skipped_reason = _skip_reason_before_decision(turn)
    if skipped_reason:
        return _skipped(skipped_reason)

    store = AgentTaskStateStore(db)
    active = store.get_active_task(
        farm_id=turn.farm_id,
        user_id=turn.user_id,
        session_id=turn.session_id,
    )
    missing = _extract_missing_information(turn.assistant_reply) or (
        _infer_missing_information_from_task_intent(turn.user_input)
    )
    if active is not None:
        return _handle_existing_task(store, turn, active, missing)

    start_reason = _start_task_reason(turn, missing)
    if not start_reason:
        return _skipped("no_task_state_signal")

    task_type = _classify_task_type(turn.user_input, turn.assistant_reply)
    task = store.upsert_active_task(
        farm_id=turn.farm_id,
        user_id=turn.user_id or "",
        session_id=turn.session_id or "",
        task_type=task_type,
        goal=_compact_text(turn.user_input),
        entities=_extract_entities(turn.user_input),
        observations=_initial_observations(turn),
        missing_information=missing,
        next_action=_next_action_for_missing(missing),
        status=TaskStateStatus.WAITING_USER if missing else TaskStateStatus.ACTIVE,
    )
    return TaskStateUpdateResult(
        action="created",
        reason=start_reason,
        task_id=task.task_id,
        task_type=task_type,
        missing_information=missing,
    )


def _handle_existing_task(
    store: AgentTaskStateStore,
    turn: TaskStateTurn,
    active,
    missing: list[str],
) -> TaskStateUpdateResult:
    if _is_cancel_turn(turn):
        task = store.mark_cancelled(
            farm_id=turn.farm_id,
            user_id=turn.user_id or "",
            session_id=turn.session_id or "",
            task_id=active.task_id,
        )
        return TaskStateUpdateResult(
            action="cancelled",
            reason="user_cancel_intent",
            task_id=task.task_id if task else active.task_id,
            task_type=active.task_type,
        )

    if _is_side_query(turn.user_input):
        return _skipped(
            "side_query", task_id=active.task_id, task_type=active.task_type
        )

    if not missing and _is_completion_turn(turn):
        task = store.mark_completed(
            farm_id=turn.farm_id,
            user_id=turn.user_id or "",
            session_id=turn.session_id or "",
            task_id=active.task_id,
        )
        return TaskStateUpdateResult(
            action="completed",
            reason="assistant_completion_signal",
            task_id=task.task_id if task else active.task_id,
            task_type=active.task_type,
        )

    return _update_existing_task(store, turn, active, missing)


def _skip_reason_before_decision(turn: TaskStateTurn) -> str:
    if not turn.user_id or not turn.session_id:
        return "missing_identity_or_session"
    if turn.pending_action is not None:
        return "pending_write_confirmation"
    if turn.pending_plan is not None and not _is_crop_cycle_setup_turn(turn):
        return "pending_write_confirmation"
    if turn.pending_decision_handled:
        return "pending_decision_handled"
    if not _compact_text(turn.user_input) or not _compact_text(turn.assistant_reply):
        return "empty_turn"
    if _is_side_query(turn.user_input):
        return "side_query"
    return ""


def _update_existing_task(
    store: AgentTaskStateStore,
    turn: TaskStateTurn,
    active,
    missing: list[str],
) -> TaskStateUpdateResult:
    observations = _merge_unique(
        list(active.observations_json or []),
        _observations_from_user_update(turn.user_input),
    )
    next_missing = missing or _remaining_missing_after_user_reply(
        list(active.missing_information_json or []),
        turn.user_input,
    )
    status = TaskStateStatus.WAITING_USER if next_missing else TaskStateStatus.ACTIVE
    task = store.upsert_active_task(
        farm_id=turn.farm_id,
        user_id=turn.user_id or "",
        session_id=turn.session_id or "",
        task_type=active.task_type,
        goal=active.goal,
        entities=_merge_entities(
            dict(active.entities_json or {}),
            _extract_entities_for_task(turn.user_input, active.task_type),
        ),
        observations=observations,
        missing_information=next_missing,
        next_action=_next_action_for_missing(next_missing) or "继续处理当前任务",
        status=status,
        expires_at=active.expires_at,
    )
    return TaskStateUpdateResult(
        action="updated",
        reason="active_task_continuation",
        task_id=task.task_id,
        task_type=task.task_type,
        missing_information=next_missing,
    )


def _start_task_reason(turn: TaskStateTurn, missing: list[str]) -> str:
    if turn.pending_plan is not None and _is_crop_cycle_setup_turn(turn):
        return "crop_cycle_setup_pending_plan"
    if not missing:
        return ""
    if _is_side_query(turn.user_input):
        return ""
    if _has_task_signal(turn.user_input):
        return "explicit_task_signal"
    if _has_natural_task_intent(turn.user_input):
        return "natural_task_intent"
    return ""


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


def _infer_missing_information_from_task_intent(user_input: str) -> list[str]:
    if _is_crop_cycle_setup_intent(user_input):
        return []
    if _has_planting_intent(user_input):
        return ["种植面积", "地块", "计划播种时间", "品种"]
    if _has_diagnosis_intent(user_input):
        return ["症状描述", "发生位置", "发生时间"]
    return []


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
    if "名称" in missing_item and _extract_planting_unit_name(text):
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
        observations.append(
            "用户已经提供：" + "、".join(_entity_observation_values(entities))
        )
    return observations


def _extract_entities(text: str) -> dict[str, object]:
    if _is_crop_cycle_setup_intent(text):
        return _extract_crop_cycle_setup_entities(text)
    return _extract_general_entities(text)


def _extract_entities_for_task(text: str, task_type: str) -> dict[str, object]:
    if task_type == "crop_cycle_setup":
        return _extract_crop_cycle_setup_entities(text)
    return _extract_entities(text)


def _extract_general_entities(text: str) -> dict[str, object]:
    crop = _extract_crop(text)
    entities = {}
    if crop:
        entities["crop"] = crop
    greenhouse = re.search(r"([\w一二三四五六七八九十\d号#-]+棚)", text)
    if greenhouse:
        entities["greenhouse"] = greenhouse.group(1)
    return entities


def _extract_crop_cycle_setup_entities(text: str) -> dict[str, object]:
    entities: dict[str, object] = {}
    crop = _extract_crop(text)
    if crop:
        entities["crop_name"] = crop
    variety = _extract_crop_variety(text)
    if variety:
        entities["variety"] = variety
    area_mu = _extract_area_mu(text)
    if area_mu is not None:
        entities["area_mu"] = area_mu

    planting_unit: dict[str, object] = {}
    unit_name = _extract_planting_unit_name(text)
    if unit_name:
        planting_unit["name"] = unit_name
        planting_unit["should_create"] = True
    if area_mu is not None and _has_planting_unit_create_intent(text):
        planting_unit["area_mu"] = area_mu
        planting_unit["should_create"] = True
    if planting_unit:
        entities["planting_unit"] = planting_unit
    return entities


def _entity_observation_values(entities: dict[str, object]) -> list[str]:
    values = []
    for value in entities.values():
        if isinstance(value, dict):
            values.extend(str(item) for item in value.values() if item)
        elif value:
            values.append(str(value))
    return values


def _merge_entities(
    base: dict[str, object], additions: dict[str, object]
) -> dict[str, object]:
    merged = dict(base)
    for key, value in additions.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


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


def _extract_crop_variety(text: str) -> str:
    matches = re.findall(r"(?<!\d)(\d{2,})(?!\d)\s*(?!亩)", text)
    return matches[0] if matches else ""


def _extract_area_mu(text: str) -> int | float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*亩", text)
    if not match:
        return None
    value = float(match.group(1))
    return int(value) if value.is_integer() else value


def _extract_planting_unit_name(text: str) -> str:
    match = re.search(r"(?:叫|命名为|名称是|名字叫)\s*([\w一-龥\d号#-]{1,20})", text)
    if not match:
        return ""
    name = match.group(1).strip(" ，,。；;！!？?")
    return name if any(keyword in name for keyword in ("棚", "地", "田", "区")) else ""


def _is_crop_cycle_setup_intent(text: str) -> bool:
    return "茬口" in text and any(
        word in text for word in ("创建", "新建", "新增", "建")
    )


def _is_crop_cycle_setup_turn(turn: TaskStateTurn) -> bool:
    return _is_crop_cycle_setup_intent(turn.user_input + turn.assistant_reply)


def _has_planting_unit_create_intent(text: str) -> bool:
    return bool(
        re.search(
            r"(?:新增|新建|创建|再建|建)\s*\d+(?:\.\d+)?\s*亩\s*(?:地|田|棚|种植单元)",
            text,
        )
        or re.search(r"(?:新增|新建|创建|再建|建).{0,8}(?:地块|大棚|种植单元)", text)
    )


def _classify_task_type(user_input: str, assistant_reply: str) -> str:
    text = user_input + assistant_reply
    if _is_crop_cycle_setup_intent(text):
        return "crop_cycle_setup"
    if any(keyword in text for keyword in ("诊断", "病害", "虫害", "症状", "叶斑")):
        return "diagnosis_followup"
    if _has_planting_intent(text):
        return "planting_plan"
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


def _has_natural_task_intent(text: str) -> bool:
    return _has_planting_intent(text) or _has_diagnosis_intent(text)


def _has_planting_intent(text: str) -> bool:
    if not _extract_crop(text):
        return False
    return any(
        keyword in text
        for keyword in (
            "想种",
            "准备种",
            "打算种",
            "计划种",
            "要种",
            "能不能种",
            "适合种",
            "种植",
            "播种",
            "定植",
        )
    )


def _has_diagnosis_intent(text: str) -> bool:
    return any(
        keyword in text
        for keyword in (
            "叶子发黄",
            "叶片发黄",
            "长斑",
            "烂根",
            "萎蔫",
            "枯萎",
            "虫",
            "病",
            "怎么处理",
            "怎么办",
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


def _skipped(
    reason: str,
    *,
    task_id: str | None = None,
    task_type: str = "",
) -> TaskStateUpdateResult:
    return TaskStateUpdateResult(
        action="skipped",
        reason=reason,
        task_id=task_id,
        task_type=task_type,
    )


__all__ = ["TaskStateTurn", "TaskStateUpdateResult", "update_task_state_after_turn"]
