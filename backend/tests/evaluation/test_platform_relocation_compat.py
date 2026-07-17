"""Evaluation 平台真实入口测试。"""

import importlib
import inspect

import pytest

pytestmark = pytest.mark.no_db


@pytest.mark.parametrize(
    "module_suffix",
    [
        "diagnostics",
        "trace_events",
        "skill_coverage",
        "discovery.rule_engine",
        "discovery.judge_worker",
        "reports.builder",
    ],
)
def test_evaluation_platform_modules_import_from_real_path(module_suffix: str):
    """Evaluation 代码应从平台真实路径导入。"""
    new_name = f"app.platforms.evaluation.{module_suffix}"

    new_module = importlib.import_module(new_name)

    assert new_module.__name__ == new_name


def test_agent_turn_service_runtime_import_uses_platform_path():
    """agent turn 运行时 discovery 规则导入应使用新平台路径。"""
    import app.services.agent_turn_service as agent_turn_service

    source = inspect.getsource(agent_turn_service._evaluate_discovery_rules)

    assert "app.platforms.evaluation.discovery.rule_engine" in source
