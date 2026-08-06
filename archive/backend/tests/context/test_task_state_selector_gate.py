"""TaskStateSelector relevance gate 测试。"""

from app.context.selectors.task_state import TaskStateSelector
from app.context.task_state.store import AgentTaskStateStore, TaskStateStatus


def test_task_state_selector_skips_context_when_relevance_gate_closed(db_session):
    AgentTaskStateStore(db_session).upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-selector-gate",
        task_type="planting_plan",
        goal="帮我规划玉米种植",
        entities={"crop": "玉米"},
        missing_information=["种植面积"],
        next_action="等待用户补充面积",
        status=TaskStateStatus.WAITING_USER,
    )

    blocks = TaskStateSelector().select(
        db=db_session,
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-selector-gate",
        task_state_should_inject=False,
    )

    assert blocks == []


def test_task_state_selector_injects_context_when_relevance_gate_open(db_session):
    task = AgentTaskStateStore(db_session).upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-selector-open",
        task_type="planting_plan",
        goal="帮我规划玉米种植",
        entities={"crop": "玉米"},
        missing_information=["种植面积"],
        next_action="等待用户补充面积",
        status=TaskStateStatus.WAITING_USER,
    )

    blocks = TaskStateSelector().select(
        db=db_session,
        farm_id=1,
        user_id="test-user-001",
        session_id="sess-selector-open",
        task_state_should_inject=True,
    )

    assert len(blocks) == 1
    assert blocks[0].key == "active_task_state"
    assert blocks[0].metadata["task_id"] == task.task_id
