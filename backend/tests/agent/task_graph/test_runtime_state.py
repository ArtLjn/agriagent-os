"""ExecutionState 状态流转测试。"""

import pytest

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

pytestmark = pytest.mark.no_db


def test_execution_state_transitions_require_context_for_waiting_and_pause() -> None:
    state = create_execution_state(execution_id="exec-1", graph_id="graph-1")

    running = start_execution(state)
    waiting = wait_for_user(running, waiting_for="confirmation")
    resumed = resume_execution(waiting)
    paused = pause_execution(resumed, pause_reason="operator backpressure")

    assert state.status == "created"
    assert running.status == "running"
    assert waiting.status == "waiting_user"
    assert waiting.waiting_for == "confirmation"
    assert resumed.status == "running"
    assert paused.status == "paused"
    assert paused.pause_reason == "operator backpressure"


def test_execution_state_rejects_invalid_waiting_and_pause_transitions() -> None:
    state = start_execution(
        create_execution_state(execution_id="exec-1", graph_id="graph-1")
    )

    with pytest.raises(ExecutionStateTransitionError):
        wait_for_user(state, waiting_for=None)
    with pytest.raises(ExecutionStateTransitionError):
        pause_execution(state, pause_reason="")


def test_execution_state_tracks_retry_counts_and_terminal_states() -> None:
    state = start_execution(
        create_execution_state(execution_id="exec-1", graph_id="graph-1")
    )

    retry1 = increment_retry(state, "node-1")
    retry2 = increment_retry(retry1, "node-1")
    failed = fail_execution(retry2, error_code="capability_timeout")
    cancelled = cancel_execution(retry2)
    completed = mark_completed(retry2)

    assert retry2.retry_counts["node-1"] == 2
    assert increment_retry(retry2, "node-1", max_retries=2).retry_limit_exceeded(
        "node-1", 2
    )
    assert failed.status == "failed"
    assert failed.last_error_code == "capability_timeout"
    assert cancelled.status == "cancelled"
    assert completed.status == "completed"


def test_terminal_transitions_clear_waiting_and_pause_context() -> None:
    running = start_execution(
        create_execution_state(execution_id="exec-1", graph_id="graph-1")
    )
    waiting = wait_for_user(running, waiting_for="confirmation")
    resumed = resume_execution(waiting)
    paused = pause_execution(resumed, pause_reason="operator backpressure")

    failed = fail_execution(paused, error_code="operator_failed")
    cancelled = cancel_execution(waiting)

    assert failed.status == "failed"
    assert failed.pause_reason is None
    assert failed.waiting_for is None
    assert failed.current_node_id is None
    assert cancelled.status == "cancelled"
    assert cancelled.waiting_for is None
