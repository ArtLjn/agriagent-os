"""Context 预热策略测试。"""

from app.context.preload import dependencies_to_preload_types


def test_dependencies_to_preload_types_keeps_order_and_skips_unknown() -> None:
    assert dependencies_to_preload_types(
        ["weather", "crop_cycles", "workers", "unknown"]
    ) == ["weather", "crop_cycle", "workers"]
