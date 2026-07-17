"""Evaluation 平台迁移兼容测试。"""

import importlib
import inspect
import sys

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
def test_legacy_evaluation_modules_alias_platform_modules(module_suffix: str):
    """旧 evaluation 路径应解析到新平台模块的同一对象。"""
    new_name = f"app.platforms.evaluation.{module_suffix}"
    old_name = f"app.evaluation.{module_suffix}"

    new_module = importlib.import_module(new_name)
    old_module = importlib.import_module(old_name)

    assert old_module is new_module
    assert sys.modules[old_name] is new_module
    assert sys.modules[new_name] is new_module


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
def test_legacy_evaluation_modules_alias_when_imported_first(module_suffix: str):
    """旧路径先导入时也不应产生第二份模块对象。"""
    old_name = f"app.evaluation.{module_suffix}"
    new_name = f"app.platforms.evaluation.{module_suffix}"

    old_module = importlib.import_module(old_name)
    new_module = importlib.import_module(new_name)

    assert old_module is new_module
    assert sys.modules[old_name] is new_module


def test_legacy_evaluation_root_aliases_platform_root():
    """旧 evaluation 包入口应转发到平台 evaluation 包对象。"""
    legacy_root = importlib.import_module("app.evaluation")
    platform_root = importlib.import_module("app.platforms.evaluation")

    assert legacy_root is platform_root


def test_agent_turn_service_runtime_import_uses_platform_path():
    """agent turn 运行时 discovery 规则导入应使用新平台路径。"""
    import app.services.agent_turn_service as agent_turn_service

    source = inspect.getsource(agent_turn_service._evaluate_discovery_rules)

    assert "app.platforms.evaluation.discovery.rule_engine" in source
    assert "app.evaluation.discovery.rule_engine" not in source
