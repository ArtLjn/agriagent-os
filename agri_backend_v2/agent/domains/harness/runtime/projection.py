"""Agent SSE 的用户视图与管理员调试视图投影。"""

from __future__ import annotations

from typing import Any, Literal

from agent.domains.harness.observability.trace.safety import sanitize_payload

PresentationProfile = Literal["user", "admin_debug"]

_ADMIN_ROLE = "admin"
_MAX_PUBLIC_PAYLOAD_CHARS = 8_000
_MAX_DEBUG_PAYLOAD_CHARS = 16_000


class ProjectionPermissionError(ValueError):
    """请求的 SSE 视觉投影超出 viewer 权限。"""


def resolve_presentation_profile(
    *,
    execution_identity: dict[str, Any],
    viewer_identity: dict[str, Any],
    requested: str | None,
) -> PresentationProfile:
    """分离执行身份和查看身份，防止 user token 获得调试字段。"""
    viewer_is_admin = viewer_identity.get("role") == _ADMIN_ROLE
    profile = requested or (
        "admin_debug"
        if viewer_is_admin and viewer_identity.get("user_id") == execution_identity.get("user_id")
        else "user"
    )
    if profile not in {"user", "admin_debug"}:
        raise ProjectionPermissionError("presentation_profile 不受支持")
    if profile == "admin_debug" and not viewer_is_admin:
        raise ProjectionPermissionError("只有管理员 viewer 可以查看调试字段")
    return profile  # type: ignore[return-value]


def project_event(
    event: dict[str, Any],
    *,
    profile: PresentationProfile,
    execution_identity: dict[str, Any],
    viewer_identity: dict[str, Any],
) -> dict[str, Any] | None:
    """在 SSE 输出边界过滤字段；Runtime/Redis 内部事件不被修改。"""
    if profile == "admin_debug":
        projected = dict(event)
        projected["data"] = sanitize_payload(
            event.get("data", {}), max_chars=_MAX_DEBUG_PAYLOAD_CHARS
        )
        projected["presentation_profile"] = profile
        projected["viewer_user_id"] = str(viewer_identity.get("user_id") or "")
        projected["execution_user_id"] = str(execution_identity.get("user_id") or "")
        projected["impersonation"] = (
            projected["viewer_user_id"] != projected["execution_user_id"]
        )
        return projected

    event_type = str(event.get("type") or "")
    data = event.get("data")
    if not isinstance(data, dict):
        data = {}
    public_event = _public_event(event_type, data)
    if public_event is None:
        return None
    projected = {"type": public_event[0], "data": public_event[1]}
    # 用户端需要 turn_id 访问重放入口，但不应看到 seq、Trace 或身份诊断字段。
    for field in ("event_id", "turn_id", "conversation_id"):
        if event.get(field):
            projected[field] = event[field]
    return projected


def _public_event(event_type: str, data: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
    if event_type in {"thought", "assistant_delta", "tool_call_delta", "plan"}:
        return None
    if event_type in {"queued", "accepted", "started", "action", "tool_started", "tool_finished", "observation"}:
        return "progress", {"message": "正在处理请求"}
    if event_type in {"step.started", "step.completed"}:
        return "progress", {
            "message": "正在执行任务步骤",
            "phase": str(data.get("status") or "running"),
        }
    if event_type in {"tool.failed", "error"}:
        error = data.get("error") if isinstance(data.get("error"), dict) else data
        return "error", {
            "message": str(error.get("message") or "业务工具执行失败"),
        }
    if event_type == "approval_required":
        return "approval_required", {
            "action_id": str(data.get("action_id") or data.get("turn_id") or ""),
            "skill_name": str(data.get("tool_name") or "业务操作"),
            "params": sanitize_payload(data.get("arguments") or {}, max_chars=_MAX_PUBLIC_PAYLOAD_CHARS),
            "context": None,
        }
    if event_type == "approval_result":
        return "approval_result", {
            "decision": data.get("decision"),
            "reason": str(data.get("reason") or "") or None,
        }
    if event_type == "operation_committed":
        return "operation_committed", {"result": _public_result(data.get("result"))}
    if event_type == "context_usage":
        return "context_usage", {
            "percent": int(data.get("percent") or 0),
            "level": str(data.get("level") or "green"),
        }
    if event_type in {"context_compressing", "context_compressed", "retrying"}:
        return "progress", {"message": "正在整理执行状态"}
    if event_type == "turn.terminated":
        return event_type, {
            "reason": str(data.get("reason") or data.get("stop_reason") or "terminated"),
            "message": str(data.get("message") or "任务未在本轮执行预算内完成，结果可能不完整。"),
        }
    if event_type == "turn.failed":
        error = data.get("error") if isinstance(data.get("error"), dict) else {}
        return event_type, {
            "reason": str(data.get("stop_reason") or "failed"),
            "message": str(error.get("message") or "本轮执行失败，请稍后重试。"),
        }
    if event_type == "turn.completed":
        return event_type, {"message": "本轮执行已完成"}
    if event_type == "done":
        return event_type, {"status": str(data.get("status") or "completed")}
    if event_type in {"final_answer_start", "final_answer_delta", "final_answer", "cancelled", "timeout"}:
        return event_type, data
    return None


def _public_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return sanitize_payload(result, max_chars=_MAX_PUBLIC_PAYLOAD_CHARS)
    summary_keys = ("message", "summary", "status", "success")
    summary = {key: result[key] for key in summary_keys if key in result}
    return sanitize_payload(summary or {"status": "completed"}, max_chars=_MAX_PUBLIC_PAYLOAD_CHARS)


__all__ = [
    "PresentationProfile",
    "ProjectionPermissionError",
    "project_event",
    "resolve_presentation_profile",
]
