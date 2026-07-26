"""ContextEngine 主入口契约测试。"""

import pytest

from app.context import ContextBuilder, ContextEngine, ContextPlanner
from app.context.contracts import ContextBlock, ContextBuildRequest, ContextBundle
from app.context.policy import ContextPolicy
from app.context.render import ContextRenderer

pytestmark = pytest.mark.no_db


class StaticSelector:
    def __init__(self, block: ContextBlock) -> None:
        self.block = block

    def select(self, **_kwargs) -> list[ContextBlock]:
        return [self.block]


def test_context_engine_is_primary_build_entry() -> None:
    engine = ContextEngine(
        selectors=[
            StaticSelector(
                ContextBlock(
                    key="farm",
                    source="farm",
                    purpose="农场状态",
                    content="农场：默认农场",
                    priority=90,
                    token_estimate=8,
                    required=True,
                )
            )
        ],
        trace_collector=None,
    )

    bundle = engine.build(db=None, farm_id=1)

    assert isinstance(bundle, ContextBundle)
    assert [block.key for block in bundle.blocks] == ["farm"]


def test_context_builder_delegates_to_context_engine() -> None:
    builder = ContextBuilder(selectors=[], trace_collector=None)

    assert isinstance(builder._engine, ContextEngine)


def test_context_planner_wraps_policy_resolution() -> None:
    request = ContextBuildRequest(farm_id=1, selected_tool_names=["manage_cost"])

    result = ContextPlanner(ContextPolicy()).plan(request)

    assert result.max_tokens >= 900
    assert result.selectors


def test_target_directory_entrypoints_are_importable() -> None:
    renderer = ContextRenderer()

    assert renderer.section_name_for_key("active_task_state") == "Task"
