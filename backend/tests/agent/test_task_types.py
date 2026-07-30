"""共享 TaskType 字面值一致性测试。"""

import pytest

from app.agent.task_types import TASK_TYPE_VALUES, TaskType
from app.agent.task_graph.models import TaskType as TaskGraphTaskType

pytestmark = pytest.mark.no_db


def test_shared_task_type_values_cover_runtime_and_planning_tasks() -> None:
    assert TASK_TYPE_VALUES == (
        "planting_plan",
        "crop_cycle_setup",
        "field_work_assignment",
        "inventory_management",
        "cost_analysis",
        "pest_diagnosis",
        "retry_or_resume",
        "legacy_skill_fallback",
    )


def test_task_graph_reuses_shared_task_type_definition() -> None:
    assert TaskGraphTaskType is TaskType
