"""Context selector 归位兼容测试。"""

import importlib

import pytest

pytestmark = pytest.mark.no_db


def test_lightweight_selector_legacy_modules_alias_to_core_module() -> None:
    core = importlib.import_module("app.context.selectors.core")

    for module_name in (
        "conversation",
        "cycle",
        "farm",
        "ledger",
        "retrieval",
        "user_settings",
        "weather",
    ):
        legacy = importlib.import_module(f"app.context.selectors.{module_name}")

        assert legacy is core


def test_selector_package_exports_resolve_from_real_modules() -> None:
    selectors = importlib.import_module("app.context.selectors")
    core = importlib.import_module("app.context.selectors.core")
    memory = importlib.import_module("app.context.selectors.memory")
    planting = importlib.import_module("app.context.selectors.planting")

    assert selectors.FarmSelector is core.FarmSelector
    assert selectors.CycleSelector is core.CycleSelector
    assert selectors.ConversationSelector is core.ConversationSelector
    assert selectors.MemorySelector is memory.MemorySelector
    assert selectors.PlantingUnitSelector is planting.PlantingUnitSelector
