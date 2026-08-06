"""Context source catalog。

本模块是 Context Builder 和 Policy 之间的 selector 组装入口。具体 selector
实现仍位于 ``app.context.selectors``，这里集中维护：

- 六类 source 分组到 selector class 的映射；
- 默认构建顺序和策略基础顺序；
- skill/router context dependency 到 block key 的映射；
- 旧 ``app.context.sources.<group>`` 导入路径的轻量兼容。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Final

from app.context.selectors import (
    ConversationSelector,
    CostCategorySelector,
    CycleSelector,
    FarmSelector,
    KnowledgeSelector,
    LedgerSelector,
    MemorySelector,
    OperationWorkOrderSelector,
    PlantingUnitSelector,
    RetrievalSelector,
    TaskStateSelector,
    UnpaidLaborSummarySelector,
    UserSettingsSelector,
    WeatherSelector,
    WorkerSelector,
)
from app.shared.compatibility import StrEnum


class ContextSourceGroup(StrEnum):
    """Context source 一级分组。"""

    ROLE_POLICY = "role_policy"
    TASK = "task"
    EVIDENCE = "evidence"
    BUSINESS = "business"
    MEMORY = "memory"
    OUTPUT_CONTRACT = "output_contract"


@dataclass(frozen=True, slots=True)
class SelectorDependencySpec:
    """context dependency 对应的 selector 和产出 block key。"""

    selector_cls: type
    block_key: str

    def __iter__(self):
        """兼容旧的 ``selector_cls, block_key = spec`` 解包方式。"""
        yield self.selector_cls
        yield self.block_key


ROLE_POLICY_SELECTOR_CLASSES: Final = (UserSettingsSelector,)
TASK_SELECTOR_CLASSES: Final = (TaskStateSelector,)
EVIDENCE_SELECTOR_CLASSES: Final = (KnowledgeSelector, RetrievalSelector)
BUSINESS_SELECTOR_CLASSES: Final = (
    FarmSelector,
    CycleSelector,
    LedgerSelector,
    UserSettingsSelector,
    WeatherSelector,
    PlantingUnitSelector,
    OperationWorkOrderSelector,
    WorkerSelector,
    UnpaidLaborSummarySelector,
    CostCategorySelector,
)
MEMORY_SELECTOR_CLASSES: Final = (ConversationSelector, MemorySelector)
OUTPUT_CONTRACT_SELECTOR_CLASSES: Final = ()

SOURCE_SELECTOR_CLASSES: Final = {
    ContextSourceGroup.ROLE_POLICY: ROLE_POLICY_SELECTOR_CLASSES,
    ContextSourceGroup.TASK: TASK_SELECTOR_CLASSES,
    ContextSourceGroup.EVIDENCE: EVIDENCE_SELECTOR_CLASSES,
    ContextSourceGroup.BUSINESS: BUSINESS_SELECTOR_CLASSES,
    ContextSourceGroup.MEMORY: MEMORY_SELECTOR_CLASSES,
    ContextSourceGroup.OUTPUT_CONTRACT: OUTPUT_CONTRACT_SELECTOR_CLASSES,
}

DEFAULT_SELECTOR_CLASSES: Final = (
    FarmSelector,
    CycleSelector,
    UserSettingsSelector,
    TaskStateSelector,
    LedgerSelector,
    WeatherSelector,
    ConversationSelector,
    MemorySelector,
    PlantingUnitSelector,
    OperationWorkOrderSelector,
    WorkerSelector,
    UnpaidLaborSummarySelector,
    CostCategorySelector,
    RetrievalSelector,
)

POLICY_BASE_SELECTOR_CLASSES: Final = (
    FarmSelector,
    UserSettingsSelector,
    CycleSelector,
    TaskStateSelector,
    MemorySelector,
    ConversationSelector,
)

DEPENDENCY_SELECTOR_SPECS: Final = {
    "crop_cycle": SelectorDependencySpec(CycleSelector, "cycle"),
    "crop_cycles": SelectorDependencySpec(CycleSelector, "cycle"),
    "active_cycles": SelectorDependencySpec(CycleSelector, "cycle"),
    "farm": SelectorDependencySpec(FarmSelector, "farm"),
    "planting_unit": SelectorDependencySpec(PlantingUnitSelector, "planting_units"),
    "planting_units": SelectorDependencySpec(PlantingUnitSelector, "planting_units"),
    "operation_work_order": SelectorDependencySpec(
        OperationWorkOrderSelector,
        "operation_work_orders",
    ),
    "operation_work_orders": SelectorDependencySpec(
        OperationWorkOrderSelector,
        "operation_work_orders",
    ),
    "recent_operations": SelectorDependencySpec(
        OperationWorkOrderSelector,
        "operation_work_orders",
    ),
    "worker": SelectorDependencySpec(WorkerSelector, "workers"),
    "workers": SelectorDependencySpec(WorkerSelector, "workers"),
    "unpaid_labor": SelectorDependencySpec(UnpaidLaborSummarySelector, "unpaid_labor"),
    "unpaid_labor_summary": SelectorDependencySpec(
        UnpaidLaborSummarySelector,
        "unpaid_labor",
    ),
    "cost_category": SelectorDependencySpec(CostCategorySelector, "cost_categories"),
    "cost_categories": SelectorDependencySpec(CostCategorySelector, "cost_categories"),
    "weather": SelectorDependencySpec(WeatherSelector, "weather"),
    "ledger": SelectorDependencySpec(LedgerSelector, "ledger"),
}


def build_selectors(selector_classes: tuple[type, ...]) -> list:
    """按给定 class 顺序实例化 selectors。"""
    return [selector_cls() for selector_cls in selector_classes]


def build_default_context_selectors() -> list:
    """返回 ContextBuilder 的默认 selector 实例顺序。"""
    return build_selectors(DEFAULT_SELECTOR_CLASSES)


def build_policy_base_selectors() -> list:
    """返回 ContextPolicy 热上下文和工作上下文的基础 selector 实例顺序。"""
    return build_selectors(POLICY_BASE_SELECTOR_CLASSES)


def source_selector_classes(group: ContextSourceGroup | str) -> tuple[type, ...]:
    """按 source 分组返回 selector classes，未知分组返回空元组。"""
    try:
        source_group = ContextSourceGroup(group)
    except ValueError:
        return ()
    return SOURCE_SELECTOR_CLASSES[source_group]


def build_source_selectors(group: ContextSourceGroup | str) -> list:
    """按 source 分组实例化 selectors。"""
    return build_selectors(source_selector_classes(group))


def selector_dependency_spec(dependency: str) -> SelectorDependencySpec | None:
    """返回 context dependency 的 selector 映射。"""
    return DEPENDENCY_SELECTOR_SPECS.get(dependency)


def _install_legacy_source_modules() -> None:
    legacy_modules = {
        "business": (
            "CostCategorySelector",
            "CycleSelector",
            "FarmSelector",
            "LedgerSelector",
            "OperationWorkOrderSelector",
            "PlantingUnitSelector",
            "UnpaidLaborSummarySelector",
            "UserSettingsSelector",
            "WeatherSelector",
            "WorkerSelector",
        ),
        "evidence": ("KnowledgeSelector", "RetrievalSelector"),
        "memory": ("ConversationSelector", "MemorySelector"),
        "output_contract": (),
        "role_policy": ("UserSettingsSelector",),
        "task": ("TaskStateSelector",),
    }
    for module_name, exported_names in legacy_modules.items():
        module = ModuleType(f"{__name__}.{module_name}")
        module.__doc__ = "兼容入口；实际维护点是 app.context.sources。"
        for exported_name in exported_names:
            setattr(module, exported_name, globals()[exported_name])
        module.__all__ = list(exported_names)
        sys.modules[module.__name__] = module
        setattr(sys.modules[__name__], module_name, module)


_install_legacy_source_modules()

__all__ = [
    "BUSINESS_SELECTOR_CLASSES",
    "ConversationSelector",
    "CostCategorySelector",
    "ContextSourceGroup",
    "DEFAULT_SELECTOR_CLASSES",
    "DEPENDENCY_SELECTOR_SPECS",
    "EVIDENCE_SELECTOR_CLASSES",
    "CycleSelector",
    "FarmSelector",
    "KnowledgeSelector",
    "LedgerSelector",
    "MEMORY_SELECTOR_CLASSES",
    "MemorySelector",
    "OperationWorkOrderSelector",
    "OUTPUT_CONTRACT_SELECTOR_CLASSES",
    "POLICY_BASE_SELECTOR_CLASSES",
    "PlantingUnitSelector",
    "ROLE_POLICY_SELECTOR_CLASSES",
    "RetrievalSelector",
    "SOURCE_SELECTOR_CLASSES",
    "SelectorDependencySpec",
    "TASK_SELECTOR_CLASSES",
    "TaskStateSelector",
    "UnpaidLaborSummarySelector",
    "UserSettingsSelector",
    "WeatherSelector",
    "WorkerSelector",
    "build_default_context_selectors",
    "build_policy_base_selectors",
    "build_selectors",
    "build_source_selectors",
    "selector_dependency_spec",
    "source_selector_classes",
]
