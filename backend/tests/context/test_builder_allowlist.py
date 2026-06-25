# backend/tests/context/test_builder_allowlist.py
"""ContextBuilder 白名单过滤集成测。"""
from app.context.builder import ContextBuilder
from app.context.models import ContextBlock
from app.context.allowlist import FORBIDDEN_CONTEXT_KEYS


class _FakeSelector:
    def __init__(self, blocks: list[ContextBlock]):
        self._blocks = blocks

    def select(self, **kwargs) -> list[ContextBlock]:
        return list(self._blocks)


class TestBuilderAllowlistFilter:
    def test_forbidden_blocks_are_dropped(self):
        forbidden_block = ContextBlock(
            key="weather_snapshot",
            source="test",
            purpose="should be filtered",
            content="天气：晴 30℃",
            priority=10,
        )
        allowed_block = ContextBlock(
            key="farm_profile",
            source="test",
            purpose="should remain",
            content="农场：测试农场",
            priority=10,
        )
        builder = ContextBuilder(
            selectors=[_FakeSelector([forbidden_block, allowed_block])],
            max_tokens=2000,
        )
        bundle = builder.build(db=None, farm_id=1)  # type: ignore[arg-type]
        keys = {b.key for b in bundle.blocks}
        assert "weather_snapshot" not in keys
        assert "farm_profile" in keys

    def test_forbidden_blocks_recorded_in_metadata(self):
        forbidden_block = ContextBlock(
            key="farm_status_snapshot",
            source="test",
            purpose="should be dropped",
            content="农场状态快照",
            priority=10,
        )
        builder = ContextBuilder(
            selectors=[_FakeSelector([forbidden_block])],
            max_tokens=2000,
        )
        bundle = builder.build(db=None, farm_id=1)  # type: ignore[arg-type]
        filtered_keys = bundle.metadata.get("allowlist_filtered_keys", [])
        assert "farm_status_snapshot" in filtered_keys

    def test_all_forbidden_keys_covered(self):
        """契约测试：白名单的所有禁止字段都被过滤。"""
        for key in FORBIDDEN_CONTEXT_KEYS:
            block = ContextBlock(
                key=key,
                source="test",
                purpose="test",
                content=f"data for {key}",
                priority=10,
            )
            builder = ContextBuilder(
                selectors=[_FakeSelector([block])],
                max_tokens=2000,
            )
            bundle = builder.build(db=None, farm_id=1)  # type: ignore[arg-type]
            assert key not in {b.key for b in bundle.blocks}, (
                f"forbidden key {key} was not filtered"
            )
