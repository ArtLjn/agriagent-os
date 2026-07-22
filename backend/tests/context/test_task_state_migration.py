"""Task Context 迁移结构测试。"""

from pathlib import Path


def test_agent_task_states_has_model_and_migration() -> None:
    model_path = Path("app/context/task_state_models.py")
    versions_dir = Path("alembic/versions")

    assert model_path.exists()
    migration_text = "\n".join(
        path.read_text(encoding="utf-8") for path in versions_dir.glob("*.py")
    )
    assert "agent_task_states" in migration_text
    for column in [
        "task_id",
        "farm_id",
        "user_id",
        "session_id",
        "task_type",
        "goal",
        "entities_json",
        "observations_json",
        "missing_information_json",
        "next_action",
        "status",
        "expires_at",
    ]:
        assert column in migration_text
