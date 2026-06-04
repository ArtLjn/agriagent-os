"""Agent state schema tests."""

from app.agent.state import AgentState


def test_agent_state_declares_user_context() -> None:
    hints = AgentState.__annotations__

    assert "user_id" in hints
    assert "session_id" in hints
