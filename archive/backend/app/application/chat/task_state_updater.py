"""聊天轮次结束后的 TaskState 最小写入入口。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.application.chat.task_state_entities import (
    classify_task_type,
    entity_observation_values,
    entity_source_for_existing_task,
    extract_entities,
    extract_entities_for_task,
    extract_planting_plan_entities,
    has_diagnosis_intent,
    has_natural_task_intent,
    has_planting_intent,
    has_task_signal,
    is_crop_cycle_setup_intent,
    merge_entities,
    next_action_for_task,
    planting_plan_missing_from_entities,
    remaining_missing_after_user_reply_for_task,
)
from app.context.task_state import AgentTaskStateStore, TaskStateStatus


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
    turn_result: TurnResult | None = None


@dataclass(frozen=True)
class TurnResult:
    """Planner/Executor 输出的结构化轮次结果。"""

    intent: str = ""
    task_type: str = ""
    entities: dict[str, object] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    plan_result: dict[str, object] | None = None
    execution_result: dict[str, object] | None = None
    facts: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskStateUpdateResult:
    """TaskState 收尾决策结果，用于后续 trace 观测。"""

    action: str
    reason: str = ""
    task_id: str | None = None
    task_type: str = ""
    missing_information: list[str] = field(default_factory=list)
    source: str = "reply_regex"


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
    structured_result = _update_from_turn_result(store, turn, active)
    if structured_result is not None:
        return structured_result
    pending_completion = _complete_existing_task_after_pending_decision(
        store, turn, active
    )
    if pending_completion is not None:
        return pending_completion
    missing = _extract_missing_information(turn.assistant_reply) or (
        _infer_missing_information_from_task_intent(turn.user_input)
    )
    if active is not None:
        return _handle_existing_task(store, turn, active, missing)

    start_reason = _start_task_reason(turn, missing)
    if not start_reason:
        return _skipped("no_task_state_signal")

    task_type = classify_task_type(turn.user_input, turn.assistant_reply)
    entities = extract_entities(turn.user_input)
    if task_type == "planting_plan":
        missing = planting_plan_missing_from_entities(missing, entities)
    return _create_new_task_state(
        store=store,
        turn=turn,
        task_type=task_type,
        entities=entities,
        missing=missing,
        start_reason=start_reason,
    )


def _update_from_turn_result(
    store: AgentTaskStateStore,
    turn: TaskStateTurn,
    active,
) -> TaskStateUpdateResult | None:
    result = turn.turn_result
    if result is None or not _has_structured_task_signal(result):
        return None
    execution_status = _execution_status(result)
    if active is not None and execution_status in {"completed", "success"}:
        task = store.mark_completed(
            farm_id=turn.farm_id,
            user_id=turn.user_id or "",
            session_id=turn.session_id or "",
            task_id=active.task_id,
        )
        return TaskStateUpdateResult(
            action="completed",
            reason="turn_result_execution_completed",
            task_id=task.task_id if task else active.task_id,
            task_type=active.task_type,
            source="turn_result",
        )
    if active is not None and execution_status in {"cancelled", "canceled"}:
        task = store.mark_cancelled(
            farm_id=turn.farm_id,
            user_id=turn.user_id or "",
            session_id=turn.session_id or "",
            task_id=active.task_id,
        )
        return TaskStateUpdateResult(
            action="cancelled",
            reason="turn_result_execution_cancelled",
            task_id=task.task_id if task else active.task_id,
            task_type=active.task_type,
            source="turn_result",
        )

    task_type = result.task_type or (active.task_type if active is not None else "")
    if not task_type:
        return None
    entities = _structured_entities(result, active)
    missing = list(result.missing_slots)
    status = TaskStateStatus.WAITING_USER if missing else TaskStateStatus.ACTIVE
    observations = _structured_observations(turn, result, active)
    task = store.upsert_active_task(
        farm_id=turn.farm_id,
        user_id=turn.user_id or "",
        session_id=turn.session_id or "",
        task_type=task_type,
        goal=active.goal if active is not None else _compact_text(turn.user_input),
        entities=entities,
        observations=observations,
        missing_information=missing,
        next_action=next_action_for_task(task_type, missing, entities)
        or "继续处理当前任务",
        status=status,
        expires_at=active.expires_at if active is not None else None,
    )
    return TaskStateUpdateResult(
        action="updated" if active is not None else "created",
        reason="turn_result_structured",
        task_id=task.task_id,
        task_type=task.task_type,
        missing_information=missing,
        source="turn_result",
    )


def _has_structured_task_signal(result: TurnResult) -> bool:
    return bool(
        result.task_type
        or result.entities
        or result.missing_slots
        or result.plan_result
        or result.execution_result
        or result.facts
    )


def _execution_status(result: TurnResult) -> str:
    payload = result.execution_result or {}
    return str(payload.get("status") or "").strip().lower()


def _structured_entities(result: TurnResult, active) -> dict[str, object]:
    entities = dict(active.entities_json or {}) if active is not None else {}
    entities.update(result.entities)
    entities.update(result.facts)
    return entities


def _structured_observations(
    turn: TaskStateTurn,
    result: TurnResult,
    active,
) -> list[str]:
    observations = list(active.observations_json or []) if active is not None else []
    if result.plan_result:
        observations = _merge_unique(observations, ["结构化规划结果已更新"])
    if result.execution_result:
        observations = _merge_unique(observations, ["结构化执行结果已更新"])
    if result.entities or result.facts:
        observations = _merge_unique(
            observations,
            [f"用户补充：{_compact_text(turn.user_input)}"],
        )
    return observations


def _create_new_task_state(
    *,
    store: AgentTaskStateStore,
    turn: TaskStateTurn,
    task_type: str,
    entities: dict[str, object],
    missing: list[str],
    start_reason: str,
) -> TaskStateUpdateResult:
    task = store.upsert_active_task(
        farm_id=turn.farm_id,
        user_id=turn.user_id or "",
        session_id=turn.session_id or "",
        task_type=task_type,
        goal=_compact_text(turn.user_input),
        entities=entities,
        observations=_initial_observations(turn),
        missing_information=missing,
        next_action=next_action_for_task(task_type, missing, entities),
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

    if (
        active.task_type != "crop_cycle_setup"
        and not missing
        and _is_completion_turn(turn)
    ):
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
    if not _compact_text(turn.user_input):
        return "empty_turn"
    if not _compact_text(turn.assistant_reply) and turn.turn_result is None:
        return "empty_turn"
    if _is_side_query(turn.user_input):
        return "side_query"
    return ""


def _complete_existing_task_after_pending_decision(
    store: AgentTaskStateStore,
    turn: TaskStateTurn,
    active,
) -> TaskStateUpdateResult | None:
    if not turn.pending_decision_handled:
        return None
    if active is None:
        return _skipped("pending_decision_handled")
    if active.task_type != "crop_cycle_setup":
        return _skipped(
            "pending_decision_handled",
            task_id=active.task_id,
            task_type=active.task_type,
        )
    if not _is_successful_pending_execution(turn.assistant_reply):
        return _skipped(
            "pending_decision_handled",
            task_id=active.task_id,
            task_type=active.task_type,
        )
    task = store.mark_completed(
        farm_id=turn.farm_id,
        user_id=turn.user_id or "",
        session_id=turn.session_id or "",
        task_id=active.task_id,
    )
    return TaskStateUpdateResult(
        action="completed",
        reason="pending_plan_completed",
        task_id=task.task_id if task else active.task_id,
        task_type=active.task_type,
    )


def _is_successful_pending_execution(reply: str) -> bool:
    text = _compact_text(reply)
    if not text.startswith("已执行"):
        return False
    return not any(keyword in text for keyword in ("失败", "不存在", "执行受阻"))


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
    entity_source = entity_source_for_existing_task(
        active.task_type, active.goal, turn.user_input
    )
    merged_entities = merge_entities(
        dict(active.entities_json or {}),
        extract_entities_for_task(entity_source, active.task_type),
    )
    next_missing = missing or remaining_missing_after_user_reply_for_task(
        list(active.missing_information_json or []),
        turn.user_input,
        active.task_type,
        merged_entities,
    )
    status = TaskStateStatus.WAITING_USER if next_missing else TaskStateStatus.ACTIVE
    task = store.upsert_active_task(
        farm_id=turn.farm_id,
        user_id=turn.user_id or "",
        session_id=turn.session_id or "",
        task_type=active.task_type,
        goal=active.goal,
        entities=merged_entities,
        observations=observations,
        missing_information=next_missing,
        next_action=next_action_for_task(
            active.task_type,
            next_missing,
            merged_entities,
        )
        or "继续处理当前任务",
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
    if has_task_signal(turn.user_input):
        return "explicit_task_signal"
    if has_natural_task_intent(turn.user_input):
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

    items: list[str] = []
    for candidate in candidates:
        items.extend(_split_missing_items(candidate))
    return _merge_unique([], items)[:6]


def _infer_missing_information_from_task_intent(user_input: str) -> list[str]:
    if is_crop_cycle_setup_intent(user_input):
        return []
    if has_planting_intent(user_input):
        return planting_plan_missing_from_entities(
            ["种植面积", "地块", "计划播种时间", "品种"],
            extract_planting_plan_entities(user_input),
        )
    if has_diagnosis_intent(user_input):
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
    item = re.sub(r"^(以下|这些|如下)?关键信息[:：]?$", "", item)
    item = re.sub(r"(吗|呢|是多少|是什么)$", "", item)
    return item.strip(" ：:，,。；;？? ")


def _observations_from_user_update(user_input: str) -> list[str]:
    if _is_greeting(user_input):
        return []
    return [f"用户补充：{_compact_text(user_input)}"]


def _initial_observations(turn: TaskStateTurn) -> list[str]:
    entities = extract_entities(turn.user_input)
    observations = []
    if entities:
        observations.append(
            "用户已经提供：" + "、".join(entity_observation_values(entities))
        )
    return observations


def _is_crop_cycle_setup_turn(turn: TaskStateTurn) -> bool:
    return is_crop_cycle_setup_intent(turn.user_input + turn.assistant_reply)


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


__all__ = [
    "TaskStateTurn",
    "TaskStateUpdateResult",
    "TurnResult",
    "update_task_state_after_turn",
]
