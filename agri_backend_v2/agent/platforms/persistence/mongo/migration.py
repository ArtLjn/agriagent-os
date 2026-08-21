"""Conversation snapshot 迁移规划与校验。

迁移器只负责从用户可见 ``conversationMessages`` 生成候选
``conversationStates``，默认不覆盖已有 state、不删除历史消息。真实写入由
CLI 的 ``--allow-write`` 显式开启，报告可作为归档和回滚依据。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass
class SnapshotValidation:
    """单个租户会话的迁移校验结果。"""

    user_id: str
    farm_id: int | None
    conversation_id: str
    message_count: int
    complete_turn_count: int
    issue_codes: list[str] = field(default_factory=list)

    @property
    def divergent(self) -> bool:
        return bool(self.issue_codes)


def group_messages(
    messages: Iterable[dict[str, Any]],
) -> dict[tuple[str, str, int | None], list[dict[str, Any]]]:
    """按可信租户和 conversation 分组，拒绝无租户消息进入迁移。"""
    groups: dict[tuple[str, str, int | None], list[dict[str, Any]]] = defaultdict(list)
    for message in messages:
        user_id = str(message.get("userId") or message.get("user_id") or "")
        conversation_id = str(
            message.get("conversationId") or message.get("conversation_id") or ""
        )
        farm_value = message.get("farmId", message.get("farm_id"))
        farm_id = int(farm_value) if farm_value not in (None, "") else None
        if user_id and conversation_id:
            groups[(user_id, conversation_id, farm_id)].append(dict(message))
    return groups


def validate_snapshot(
    messages: list[dict[str, Any]],
    existing_state: dict[str, Any] | None = None,
) -> SnapshotValidation:
    """校验完整 Turn、租户范围和摘要来源，不修改输入数据。"""
    first = messages[0] if messages else {}
    user_id = str(first.get("userId") or first.get("user_id") or "")
    farm_value = first.get("farmId", first.get("farm_id"))
    farm_id = int(farm_value) if farm_value not in (None, "") else None
    conversation_id = str(
        first.get("conversationId") or first.get("conversation_id") or ""
    )
    issues: list[str] = []
    if not user_id or not conversation_id or farm_id is None:
        issues.append("tenant_scope_missing")
    turn_roles: dict[str, set[str]] = defaultdict(set)
    for message in messages:
        turn_id = str(message.get("turnId") or message.get("turn_id") or "")
        role = str(message.get("role") or "")
        if not turn_id or role not in {"user", "assistant"}:
            issues.append("message_identity_incomplete")
            continue
        turn_roles[turn_id].add(role)
    complete_turns = sum(
        roles == {"user", "assistant"} for roles in turn_roles.values()
    )
    if any(roles != {"user", "assistant"} for roles in turn_roles.values()):
        issues.append("incomplete_turn")
    if existing_state:
        state_user = str(
            existing_state.get("userId") or existing_state.get("user_id") or ""
        )
        state_conversation = str(
            existing_state.get("conversationId")
            or existing_state.get("conversation_id")
            or ""
        )
        if state_user != user_id or state_conversation != conversation_id:
            issues.append("state_tenant_mismatch")
        revision = int(
            existing_state.get(
                "conversationRevision", existing_state.get("conversation_revision", 0)
            )
            or 0
        )
        summary_source = existing_state.get(
            "summarySourceConversationRevision",
            existing_state.get("summary_source_conversation_revision"),
        )
        if summary_source is not None and int(summary_source or 0) > revision:
            issues.append("summary_source_revision_ahead")
    return SnapshotValidation(
        user_id=user_id,
        farm_id=farm_id,
        conversation_id=conversation_id,
        message_count=len(messages),
        complete_turn_count=complete_turns,
        issue_codes=sorted(set(issues)),
    )


def build_state_candidate(
    messages: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """生成只包含状态投影的候选文档，不复制消息全文。"""
    validation = validate_snapshot(messages)
    current = now or datetime.now(timezone.utc)
    iso = current.isoformat().replace("+00:00", "Z")
    return {
        "userId": validation.user_id,
        "farmId": validation.farm_id,
        "conversationId": validation.conversation_id,
        "sessionId": validation.conversation_id,
        "conversationRevision": validation.complete_turn_count,
        "summaryRevision": 0,
        "resetGeneration": 0,
        "summaryStatus": "stale" if validation.complete_turn_count else "empty",
        "summarySourceConversationRevision": None,
        "migration": {
            "source": "conversationMessages",
            "messageCount": validation.message_count,
            "completeTurnCount": validation.complete_turn_count,
            "validatedAt": iso,
            "issueCodes": validation.issue_codes,
        },
        "createdAt": iso,
        "updatedAt": iso,
    }


def build_migration_report(
    messages: Iterable[dict[str, Any]],
    existing_states: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """生成可归档、可审计的迁移报告和候选 state。"""
    groups = group_messages(messages)
    state_map = {
        (
            str(state.get("userId") or state.get("user_id") or ""),
            str(state.get("conversationId") or state.get("conversation_id") or ""),
            _farm_id(state),
        ): state
        for state in existing_states
    }
    entries: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        validation = validate_snapshot(group, state_map.get(key))
        entry = asdict(validation)
        entry["action"] = "validate_only" if key in state_map else "create_candidate"
        entry["candidate"] = None if key in state_map else build_state_candidate(group)
        entries.append(entry)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source": "conversationMessages",
        "target": "conversationStates",
        "delete_performed": False,
        "rollback": {
            "can_rollback": True,
            "created_state_keys": [],
            "protected_collections": [
                "conversationMessages",
                "memoryObservations",
            ],
            "strategy": "only remove state keys recorded after explicit allow-write",
        },
        "total_conversations": len(entries),
        "divergence_count": sum(bool(item["issue_codes"]) for item in entries),
        "entries": entries,
    }


def _farm_id(document: dict[str, Any]) -> int | None:
    value = document.get("farmId", document.get("farm_id"))
    return int(value) if value not in (None, "") else None


__all__ = [
    "SnapshotValidation",
    "build_migration_report",
    "build_state_candidate",
    "group_messages",
    "validate_snapshot",
]
