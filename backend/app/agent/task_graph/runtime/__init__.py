"""Legacy Task Graph Runtime 骨架。

该包仅作为 task_graph planning compile artifact 的历史测试与兼容边界保留；
长期生产 Runtime 是 pending_plan + task_state。
"""

from app.agent.task_graph.runtime.scheduler import next_runnable_nodes
from app.agent.task_graph.runtime.state import (
    ExecutionStateTransitionError,
    cancel_execution,
    create_execution_state,
    fail_execution,
    increment_retry,
    mark_completed,
    pause_execution,
    resume_execution,
    start_execution,
    wait_for_user,
)

LEGACY_RUNTIME_STATUS = "legacy_planning_compile_artifact"

__all__ = [
    "ExecutionStateTransitionError",
    "LEGACY_RUNTIME_STATUS",
    "cancel_execution",
    "create_execution_state",
    "fail_execution",
    "increment_retry",
    "mark_completed",
    "next_runnable_nodes",
    "pause_execution",
    "resume_execution",
    "start_execution",
    "wait_for_user",
]
