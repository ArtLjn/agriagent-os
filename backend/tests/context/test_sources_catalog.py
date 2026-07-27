"""Context sources catalog 契约测试。"""

import importlib

import pytest

from app.context.builder import default_context_selectors
from app.context.sources import (
    ContextSourceGroup,
    FarmSelector,
    LedgerSelector,
    TaskStateSelector,
    build_policy_base_selectors,
    build_source_selectors,
    selector_dependency_spec,
    source_selector_classes,
)

pytestmark = pytest.mark.no_db


def _selector_names(selectors: list) -> list[str]:
    return [selector.__class__.__name__ for selector in selectors]


def test_sources_catalog_groups_selector_classes_by_context_source() -> None:
    business_classes = source_selector_classes(ContextSourceGroup.BUSINESS)

    assert FarmSelector in business_classes
    assert LedgerSelector in business_classes
    assert source_selector_classes("unknown") == ()

    task_selectors = build_source_selectors("task")
    assert len(task_selectors) == 1
    assert isinstance(task_selectors[0], TaskStateSelector)


def test_sources_catalog_keeps_default_and_policy_orders_explicit() -> None:
    assert _selector_names(default_context_selectors()) == [
        "FarmSelector",
        "CycleSelector",
        "UserSettingsSelector",
        "TaskStateSelector",
        "LedgerSelector",
        "WeatherSelector",
        "ConversationSelector",
        "MemorySelector",
        "PlantingUnitSelector",
        "OperationWorkOrderSelector",
        "WorkerSelector",
        "UnpaidLaborSummarySelector",
        "CostCategorySelector",
        "RetrievalSelector",
    ]
    assert _selector_names(build_policy_base_selectors()) == [
        "FarmSelector",
        "UserSettingsSelector",
        "CycleSelector",
        "TaskStateSelector",
        "MemorySelector",
        "ConversationSelector",
    ]


def test_sources_catalog_maps_dependencies_to_block_keys() -> None:
    spec = selector_dependency_spec("operation_work_orders")

    assert spec is not None
    assert spec.selector_cls.__name__ == "OperationWorkOrderSelector"
    assert spec.block_key == "operation_work_orders"
    selector_cls, block_key = spec
    assert selector_cls is spec.selector_cls
    assert block_key == spec.block_key


def test_legacy_source_submodule_imports_stay_compatible() -> None:
    business = importlib.import_module("app.context.sources.business")
    evidence = importlib.import_module("app.context.sources.evidence")
    output_contract = importlib.import_module("app.context.sources.output_contract")

    assert business.FarmSelector is FarmSelector
    assert evidence.RetrievalSelector.__name__ == "RetrievalSelector"
    assert output_contract.__all__ == []


def test_flattened_context_modules_keep_legacy_submodule_imports() -> None:
    budget = importlib.import_module("app.context.pipeline.budget")
    renderer = importlib.import_module("app.context.pipeline.renderer")
    compression = importlib.import_module("app.context.pipeline.compression")
    compressor_text = importlib.import_module("app.context.pipeline.compressors.text")
    rag = importlib.import_module("app.context.knowledge.rag")
    runtime_cache = importlib.import_module("app.context.runtime.cache")
    runtime_preload = importlib.import_module("app.context.runtime.preload")
    runtime_trace = importlib.import_module("app.context.runtime.trace")
    runtime_invalidation = importlib.import_module("app.context.runtime.invalidation")
    task_models = importlib.import_module("app.context.task_state.models")
    task_store = importlib.import_module("app.context.task_state.store")

    assert budget.TokenBudget.__name__ == "TokenBudget"
    assert renderer.ContextRenderer.__name__ == "ContextRenderer"
    assert compression.safe_preview(" abc ") == "abc"
    assert compressor_text.compress_text("abcdef", 4) == "abc…"
    assert rag.RAGKnowledgeProvider.__name__ == "RAGKnowledgeProvider"
    assert runtime_cache.TTLCache.__name__ == "TTLCache"
    assert runtime_preload.dependencies_to_preload_types(["weather"]) == ["weather"]
    assert runtime_trace.build_context_trace_payload.__name__ == (
        "build_context_trace_payload"
    )
    assert runtime_invalidation.invalidate_farm_context.__name__ == (
        "invalidate_farm_context"
    )
    assert task_models.AgentTaskState.__name__ == "AgentTaskState"
    assert task_store.AgentTaskStateStore.__name__ == "AgentTaskStateStore"
