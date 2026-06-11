"""数据飞轮样本转仿真/评测用例草稿。"""

from typing import Any


def build_case_json(
    *,
    sample_id: str,
    sample: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, Any]:
    """从样本详情构造 regression case JSON。"""
    quality_labels = detail["quality_labels"]
    label_text = ", ".join(quality_labels) if quality_labels else "unlabeled"
    case_json = {
        "case_id": f"regression-{sample['session_id']}-{sample['turn_id']}",
        "description": f"Data flywheel regression sample {sample_id} ({label_text})",
        "user_input": _message_content(detail, "user")
        or sample.get("user_input_preview")
        or "",
        "category": quality_labels[0] if quality_labels else "data_flywheel",
        "expected_skills": [
            {"name": tool_name} for tool_name in sample["selected_tools"]
        ],
        "expected_pending_action": None,
        "confirmation_flow": [],
        "expected_database_diff": [],
        "reply_assertions": _reply_assertions(detail, sample),
        "metadata": {
            "source": "data_flywheel",
            "source_sample_id": sample_id,
            "source_session_id": sample["session_id"],
            "source_request_id": sample["request_id"],
            "quality_labels": quality_labels,
        },
    }
    case_json["expected_pending_action"] = _expected_pending_action(
        detail["pending_lifecycle"], quality_labels, sample["selected_tools"]
    )
    return case_json


def _message_content(detail: dict[str, Any], role: str) -> str | None:
    for message in detail["messages"]:
        if message.get("role") == role:
            return message.get("content")
    return None


def _reply_assertions(
    detail: dict[str, Any], sample: dict[str, Any]
) -> list[dict[str, str]]:
    reply = _message_content(detail, "assistant") or sample.get(
        "assistant_reply_preview"
    )
    return [{"contains": reply}] if reply else []


def _expected_pending_action(
    pending_lifecycle: list[dict[str, Any]],
    quality_labels: list[str],
    selected_tools: list[str],
) -> dict[str, Any] | None:
    if not pending_lifecycle and "pending_missed" not in quality_labels:
        return None
    skill_name = _pending_skill_name(pending_lifecycle) or (
        selected_tools[0] if selected_tools else ""
    )
    return {
        "skill_name": skill_name,
        "params": {},
        "status": "created",
        "confirmation_required": True,
    }


def _pending_skill_name(pending_lifecycle: list[dict[str, Any]]) -> str | None:
    for event in pending_lifecycle:
        payload = event.get("payload") or {}
        steps = payload.get("steps") if isinstance(payload, dict) else None
        if isinstance(steps, list) and steps:
            skill_name = steps[0].get("skill_name")
            if skill_name:
                return str(skill_name)
    return None
