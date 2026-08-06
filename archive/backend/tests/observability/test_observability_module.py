"""Observability module tests."""

import pytest

from app.observability import (
    AgentLifecycleEvent,
    increment_counter,
    lifecycle_event_names,
    reset_metrics,
    session_summary_generated_total,
)

pytestmark = pytest.mark.no_db


def test_lifecycle_event_names_are_exported() -> None:
    assert AgentLifecycleEvent.LLM_CALL.value in lifecycle_event_names()


def test_counter_helpers_are_exported() -> None:
    reset_metrics()
    increment_counter("session_summary_generated_total")
    assert session_summary_generated_total() == 1
