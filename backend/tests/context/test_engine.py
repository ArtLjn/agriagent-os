"""ContextBuilder 对外契约测试（不需要数据库）。"""

import pytest

from app.context import ContextBuilder
from app.context.core.models import ContextBlock, ContextBundle
from app.context.core.policy import ContextBuildRequest, ContextPolicy
from app.context.pipeline.renderer import ContextRenderer

pytestmark = pytest.mark.no_db


class StaticSelector:
    def __init__(self, block: ContextBlock) -> None:
        self.block = block

    def select(self, **_kwargs) -> list[ContextBlock]:
        return [self.block]


def test_context_builder_is_primary_build_entry() -> None:
    """ContextBuilder 是 Context 构建唯一入口，build() 返回 ContextBundle。"""
    builder = ContextBuilder(
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

    bundle = builder.build(db=None, farm_id=1)

    assert isinstance(bundle, ContextBundle)
    assert [block.key for block in bundle.blocks] == ["farm"]


def test_context_policy_resolve_returns_plan() -> None:
    """ContextPolicy.resolve 直接产出可执行的 ContextPolicyResult。"""
    request = ContextBuildRequest(farm_id=1, selected_tool_names=["manage_cost"])

    result = ContextPolicy().resolve(request)

    assert result.max_tokens >= 900
    assert result.selectors


def test_target_directory_entrypoints_are_importable() -> None:
    """目标目录的核心类型与渲染器对外可导入。"""
    renderer = ContextRenderer()

    assert renderer.section_name_for_key("active_task_state") == "Task"
