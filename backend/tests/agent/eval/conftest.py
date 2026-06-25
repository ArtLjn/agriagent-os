"""Eval 公共 fixture。"""
from unittest.mock import MagicMock

import pytest

from app.context.models import ContextBlock, ContextBundle


@pytest.fixture()
def mock_skill_registry():
    """mock Skill registry 的 execute 方法。"""
    registry = MagicMock()
    registry.execute = MagicMock(return_value={"status": "success", "data": {}})
    return registry


@pytest.fixture()
def pollution_bundle_factory():
    """构造含违禁字段的 ContextBundle（用于污染对照测试）。"""

    def _create(pollution_data: dict[str, str]) -> ContextBundle:
        blocks = [
            ContextBlock(
                key=key,
                source="test_pollution",
                purpose="should_not_be_used",
                content=content,
                priority=10,
            )
            for key, content in pollution_data.items()
        ]
        return ContextBundle(
            blocks=blocks,
            token_budget=2000,
            token_estimate=100,
        )

    return _create


@pytest.fixture()
def eval_metrics():
    """记录 eval 指标的可变 dict。"""
    return {
        "total": 0,
        "skill_triggered_correctly": 0,
        "skill_missed": 0,
        "chitchat_false_positive": 0,
        "data_source_matches_skill": 0,
    }


@pytest.fixture()
def fake_tool_factory():
    """构造 fake tool 的工厂函数。"""

    def _create(name: str) -> MagicMock:
        tool = MagicMock()
        tool.name = name
        return tool

    return _create
