"""TaskStateSelector 测试。"""

from datetime import datetime, timedelta

from app.context.task_state_store import AgentTaskStateStore
from app.context.selectors.task_state import TaskStateSelector


def test_task_state_selector_generates_task_block(db_session) -> None:
    store = AgentTaskStateStore(db_session)
    task = store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
        task_type="plan_draft",
        goal="制定番茄补光计划",
        entities={"crop": "番茄", "greenhouse": "一号棚"},
        observations=["用户已经说明连续阴天"],
        missing_information=["补光灯功率"],
        next_action="询问补光灯功率",
        expires_at=datetime.now() + timedelta(hours=1),
    )

    blocks = TaskStateSelector().select(
        db=db_session,
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
    )

    assert len(blocks) == 1
    block = blocks[0]
    assert block.key == "active_task_state"
    assert block.source == "task_state"
    assert "目标：制定番茄补光计划" in block.content
    assert "已知实体：crop=番茄；greenhouse=一号棚" in block.content
    assert "缺失信息：补光灯功率" in block.content
    assert "下一步动作：询问补光灯功率" in block.content
    assert block.metadata["task_id"] == task.task_id
    assert block.metadata["task_type"] == "plan_draft"
    assert block.metadata["status"] == "active"
    assert "expires_at" in block.metadata


def test_task_state_selector_returns_empty_without_active_task(db_session) -> None:
    blocks = TaskStateSelector().select(
        db=db_session,
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
    )

    assert blocks == []


def test_task_state_selector_metadata_does_not_leak_large_json(db_session) -> None:
    store = AgentTaskStateStore(db_session)
    large_observation = "病斑描述" * 200
    store.upsert_active_task(
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
        task_type="diagnosis_followup",
        goal="补全诊断信息",
        entities={"crop": "黄瓜", "raw_payload": {"very_large": "x" * 500}},
        observations=[large_observation],
        missing_information=["叶背是否有霉层"],
        next_action="追问叶背症状",
    )

    block = TaskStateSelector().select(
        db=db_session,
        farm_id=1,
        user_id="test-user-001",
        session_id="session-1",
    )[0]

    assert "very_large" not in block.metadata
    assert "raw_payload" not in block.metadata
    assert large_observation not in str(block.metadata)
