"""TaskGraph runtime 收敛状态测试。"""

from pathlib import Path

import pytest

from app.agent.task_graph import runtime

pytestmark = pytest.mark.no_db


def test_task_graph_runtime_is_marked_legacy_planning_artifact() -> None:
    assert runtime.LEGACY_RUNTIME_STATUS == "legacy_planning_compile_artifact"


def test_main_app_does_not_import_task_graph_runtime_modules() -> None:
    app_dir = Path(__file__).resolve().parents[3] / "app"
    violations: list[str] = []
    for path in app_dir.rglob("*.py"):
        relative = path.relative_to(app_dir)
        if relative.parts[:3] == ("agent", "task_graph", "runtime"):
            continue
        if relative.parts[:2] == ("agent", "task_graph"):
            continue
        text = path.read_text(encoding="utf-8")
        if "app.agent.task_graph.runtime" in text:
            violations.append(str(relative))

    assert violations == []
