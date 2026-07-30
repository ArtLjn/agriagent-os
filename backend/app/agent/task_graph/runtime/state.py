"""Legacy ExecutionState 创建与状态流转辅助。

仅保留为 task_graph planning compile artifact 的兼容测试对象；生产执行状态以
PendingPlan 为准。
"""

from __future__ import annotations

from app.agent.task_graph.models import ExecutionState, WaitingFor


class ExecutionStateTransitionError(ValueError):
    pass


def create_execution_state(*, execution_id: str, graph_id: str) -> ExecutionState:
    return ExecutionState(
        execution_id=execution_id,
        graph_id=graph_id,
        status="created",
        current_node_id=None,
    )


def start_execution(state: ExecutionState) -> ExecutionState:
    if state.status not in {"created", "paused", "waiting_user", "failed"}:
        raise ExecutionStateTransitionError(f"{state.status} 不能进入 running")
    return _copy_state(state, status="running", pause_reason=None, waiting_for=None)


def wait_for_user(
    state: ExecutionState, *, waiting_for: WaitingFor | None
) -> ExecutionState:
    if state.status != "running":
        raise ExecutionStateTransitionError(f"{state.status} 不能进入 waiting_user")
    if waiting_for is None:
        raise ExecutionStateTransitionError("waiting_user 必须携带 waiting_for")
    return _copy_state(state, status="waiting_user", waiting_for=waiting_for)


def pause_execution(state: ExecutionState, *, pause_reason: str) -> ExecutionState:
    if state.status != "running":
        raise ExecutionStateTransitionError(f"{state.status} 不能进入 paused")
    if not pause_reason:
        raise ExecutionStateTransitionError("paused 必须携带 pause_reason")
    return _copy_state(state, status="paused", pause_reason=pause_reason)


def resume_execution(state: ExecutionState) -> ExecutionState:
    if state.status not in {"paused", "waiting_user", "failed"}:
        raise ExecutionStateTransitionError(f"{state.status} 不能恢复运行")
    return _copy_state(state, status="running", pause_reason=None, waiting_for=None)


def mark_completed(state: ExecutionState) -> ExecutionState:
    if state.status != "running":
        raise ExecutionStateTransitionError(f"{state.status} 不能完成")
    return _copy_state(
        state,
        status="completed",
        current_node_id=None,
        pause_reason=None,
        waiting_for=None,
    )


def fail_execution(state: ExecutionState, *, error_code: str) -> ExecutionState:
    if state.status not in {"running", "waiting_user", "paused"}:
        raise ExecutionStateTransitionError(f"{state.status} 不能失败")
    return _copy_state(
        state,
        status="failed",
        current_node_id=None,
        pause_reason=None,
        waiting_for=None,
        last_error_code=error_code,
    )


def cancel_execution(state: ExecutionState) -> ExecutionState:
    if state.status in {"completed", "cancelled"}:
        raise ExecutionStateTransitionError(f"{state.status} 不能取消")
    return _copy_state(
        state,
        status="cancelled",
        current_node_id=None,
        pause_reason=None,
        waiting_for=None,
    )


def increment_retry(
    state: ExecutionState, node_id: str, *, max_retries: int | None = None
) -> ExecutionState:
    retry_counts = dict(state.retry_counts)
    retry_counts[node_id] = retry_counts.get(node_id, 0) + 1
    dead_node_ids = list(state.dead_node_ids)
    if (
        max_retries is not None
        and retry_counts[node_id] > max_retries
        and node_id not in dead_node_ids
    ):
        dead_node_ids.append(node_id)
    return _copy_state(state, retry_counts=retry_counts, dead_node_ids=dead_node_ids)


def _copy_state(state: ExecutionState, **updates: object) -> ExecutionState:
    payload = state.model_dump(mode="python")
    payload.update(updates)
    return ExecutionState.model_validate(payload)
