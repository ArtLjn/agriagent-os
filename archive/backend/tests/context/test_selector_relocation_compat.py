"""Context selector 真实入口测试。"""

import importlib

import pytest

pytestmark = pytest.mark.no_db


def test_lightweight_selectors_resolve_from_core_module() -> None:
    core = importlib.import_module("app.context.selectors.core")

    assert core.ConversationSelector.__module__ == "app.context.selectors.core"
    assert core.CycleSelector.__module__ == "app.context.selectors.core"
    assert core.FarmSelector.__module__ == "app.context.selectors.core"
    assert core.LedgerSelector.__module__ == "app.context.selectors.core"
    assert core.RetrievalSelector.__module__ == "app.context.selectors.core"
    assert core.UserSettingsSelector.__module__ == "app.context.selectors.core"
    assert core.WeatherSelector.__module__ == "app.context.selectors.core"


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
