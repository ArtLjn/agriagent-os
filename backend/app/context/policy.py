"""Context 构建策略入口。"""

from dataclasses import dataclass, field
from typing import Protocol

from app.core.compat import StrEnum
from app.context.models import ContextBlock
from app.context.selectors import (
    ConversationSelector,
    CostCategorySelector,
    CycleSelector,
    FarmSelector,
    LedgerSelector,
    MemorySelector,
    OperationWorkOrderSelector,
    PlantingUnitSelector,
    RetrievalSelector,
    UnpaidLaborSummarySelector,
    UserSettingsSelector,
    WeatherSelector,
    WorkerSelector,
)


class ContextLayer(StrEnum):
    """Context 分层。"""

    HOT = "hot"
    WORKING = "working"
    RETRIEVAL = "retrieval"


class ContextSelector(Protocol):
    """Context selector 协议。"""

    def select(self, **kwargs) -> list[ContextBlock]: ...


@dataclass(frozen=True)
class ContextBuildRequest:
    """Context 构建请求。"""

    intent: str = "chat"
    selected_tool_names: list[str] = field(default_factory=list)
    context_dependencies: list[str] = field(default_factory=list)
    selected_skill_metadata: dict[str, dict] = field(default_factory=dict)
    farm_id: int = 0
    user_id: str | None = None
    session_id: str | None = None
    include_retrieval: bool = False


@dataclass(frozen=True)
class ContextPolicyResult:
    """Context 策略解析结果。"""

    enabled_layers: list[ContextLayer]
    selectors: list[ContextSelector]
    max_tokens: int
    dependency_map: dict[str, list[str]] = field(default_factory=dict)


class ContextPolicy:
    """根据意图和工具选择 Context 构建策略。"""

    COST_TOOLS = frozenset({"get_cost_summary", "get_debt_summary"})
    WEATHER_TOOLS = frozenset({"get_weather_forecast"})
    CROP_CYCLE_TOOLS = frozenset(
        {"update_crop_cycle", "create_crop_cycle", "update_crop_stage"}
    )
    WORK_ORDER_TOOLS = frozenset(
        {
            "create_operation_work_order",
            "get_operation_work_orders",
            "update_operation_work_order",
        }
    )
    LABOR_TOOLS = frozenset({"get_labor_payables", "settle_labor_payment"})
    COST_CATEGORY_TOOLS = frozenset(
        {"create_cost_record", "update_cost_record", "correct_cost_record"}
    )

    DEPENDENCY_SELECTORS = {
        "crop_cycle": (CycleSelector, "cycle"),
        "crop_cycles": (CycleSelector, "cycle"),
        "active_cycles": (CycleSelector, "cycle"),
        "farm": (FarmSelector, "farm"),
        "planting_unit": (PlantingUnitSelector, "planting_units"),
        "planting_units": (PlantingUnitSelector, "planting_units"),
        "operation_work_order": (
            OperationWorkOrderSelector,
            "operation_work_orders",
        ),
        "operation_work_orders": (
            OperationWorkOrderSelector,
            "operation_work_orders",
        ),
        "recent_operations": (
            OperationWorkOrderSelector,
            "operation_work_orders",
        ),
        "worker": (WorkerSelector, "workers"),
        "workers": (WorkerSelector, "workers"),
        "unpaid_labor": (UnpaidLaborSummarySelector, "unpaid_labor"),
        "unpaid_labor_summary": (UnpaidLaborSummarySelector, "unpaid_labor"),
        "cost_category": (CostCategorySelector, "cost_categories"),
        "cost_categories": (CostCategorySelector, "cost_categories"),
        "weather": (WeatherSelector, "weather"),
        "ledger": (LedgerSelector, "ledger"),
    }

    def resolve(self, request: ContextBuildRequest) -> ContextPolicyResult:
        """解析 Context 层、selector 和 token 预算。"""
        selected_tool_names = set(request.selected_tool_names)
        layers = [ContextLayer.HOT, ContextLayer.WORKING]
        selectors: list[ContextSelector] = [
            FarmSelector(),
            UserSettingsSelector(),
            CycleSelector(),
            MemorySelector(),
            ConversationSelector(),
        ]
        max_tokens = 512
        dependency_map: dict[str, list[str]] = {}

        dependencies = self._dependencies_from_request(request)
        for dependency in dependencies:
            selector_spec = self.DEPENDENCY_SELECTORS.get(dependency)
            if selector_spec is None:
                continue
            selector_cls, block_key = selector_spec
            if not any(isinstance(selector, selector_cls) for selector in selectors):
                selectors.append(selector_cls())
            dependency_map.setdefault(block_key, []).append(dependency)

        if selected_tool_names & self.COST_TOOLS:
            if not any(isinstance(selector, LedgerSelector) for selector in selectors):
                selectors.append(LedgerSelector())
            layers.append(ContextLayer.RETRIEVAL)
            max_tokens = max(max_tokens, 900)

        if selected_tool_names & self.CROP_CYCLE_TOOLS:
            max_tokens = max(max_tokens, 700)

        if selected_tool_names & self.WEATHER_TOOLS:
            if not any(isinstance(selector, WeatherSelector) for selector in selectors):
                selectors.append(WeatherSelector())
            if not any(
                isinstance(selector, RetrievalSelector) for selector in selectors
            ):
                selectors.append(RetrievalSelector())
            layers.append(ContextLayer.RETRIEVAL)

        if request.include_retrieval:
            if not any(
                isinstance(selector, RetrievalSelector) for selector in selectors
            ):
                selectors.append(RetrievalSelector())
            layers.append(ContextLayer.RETRIEVAL)

        if dependency_map:
            layers.append(ContextLayer.RETRIEVAL)
            max_tokens = max(max_tokens, 900)

        return ContextPolicyResult(
            enabled_layers=list(dict.fromkeys(layers)),
            selectors=selectors,
            max_tokens=max_tokens,
            dependency_map=dependency_map,
        )

    def _dependencies_from_request(self, request: ContextBuildRequest) -> list[str]:
        selected_tool_names = set(request.selected_tool_names)
        dependencies: list[str] = []

        def add(raw_dependencies: list[str] | set[str] | tuple[str, ...]) -> None:
            for item in raw_dependencies:
                dependency = str(item)
                if dependency not in dependencies:
                    dependencies.append(dependency)

        add(request.context_dependencies)

        for metadata in request.selected_skill_metadata.values():
            raw_dependencies = metadata.get("context_dependencies", [])
            add(raw_dependencies)

        if selected_tool_names & self.CROP_CYCLE_TOOLS:
            add(["crop_cycle"])
        if selected_tool_names & self.WORK_ORDER_TOOLS:
            add(["crop_cycle", "planting_units", "operation_work_orders", "workers"])
        if selected_tool_names & self.LABOR_TOOLS:
            add(["workers", "unpaid_labor", "ledger"])
        if selected_tool_names & self.COST_CATEGORY_TOOLS:
            add(["ledger", "cost_categories"])
        if selected_tool_names & self.WEATHER_TOOLS:
            add(["weather"])
        return dependencies


__all__ = [
    "ContextBuildRequest",
    "ContextLayer",
    "ContextPolicy",
    "ContextPolicyResult",
]
