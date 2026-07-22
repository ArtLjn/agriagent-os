"""Context 构建策略入口。"""

from dataclasses import dataclass, field
from typing import Protocol

from app.shared.compatibility import StrEnum
from app.context.models import ContextBlock
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
from app.shared.config import settings


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
    query: str = ""
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

    RAG_INTENT_HINTS = frozenset(
        {
            "query_planting_advice",
            "query_daily_operation_advice",
            "query_weather_crop_impact",
            "query_diagnosis",
            "diagnosis",
            "knowledge",
            "planting_advice",
            "plan",
            "方案",
        }
    )
    RAG_QUERY_HINTS = frozenset(
        {
            "病",
            "虫",
            "霜霉",
            "黄叶",
            "黄斑",
            "诊断",
            "防治",
            "打药",
            "施肥",
            "控旺",
            "育苗",
            "定植",
            "种植",
            "方案",
            "建议",
            "怎么办",
        }
    )
    RAG_BLOCKED_INTENT_HINTS = frozenset(
        {
            "cost",
            "finance",
            "debt",
            "labor",
            "wage",
            "pending",
            "confirm",
            "confirmation",
        }
    )
    RAG_BLOCKED_QUERY_HINTS = frozenset(
        {
            "花了",
            "多少钱",
            "账",
            "支出",
            "收入",
            "人工",
            "工资",
            "工钱",
            "确认",
            "取消",
        }
    )

    COST_TOOLS = frozenset({"manage_cost"})
    WEATHER_TOOLS = frozenset({"weather"})
    CROP_CYCLE_TOOLS = frozenset(
        {
            "manage_crop_cycle",
            "create_crop_cycle",
            "update_crop_cycle",
            "update_crop_stage",
        }
    )
    WORK_ORDER_TOOLS = frozenset(
        {
            "create_operation_work_order",
            "get_operation_work_orders",
            "update_operation_work_order",
        }
    )
    LABOR_TOOLS = frozenset({"manage_labor_payment"})
    COST_CATEGORY_TOOLS = frozenset({"manage_cost_categories"})
    PLANTING_UNIT_TOOLS = frozenset({"manage_planting_units"})

    def __init__(self, rag_enabled: bool | None = None) -> None:
        self.rag_enabled = (
            settings.rag_service.enabled if rag_enabled is None else rag_enabled
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
        selectors = self._base_selectors()
        dependency_map = self._apply_dependency_selectors(selectors, request)
        max_tokens = self._apply_tool_selectors(
            selectors,
            layers,
            selected_tool_names,
        )
        max_tokens = self._apply_retrieval_selectors(
            selectors,
            layers,
            request,
            max_tokens,
        )

        if dependency_map:
            layers.append(ContextLayer.RETRIEVAL)
            max_tokens = max(max_tokens, 900)

        return ContextPolicyResult(
            enabled_layers=list(dict.fromkeys(layers)),
            selectors=selectors,
            max_tokens=max_tokens,
            dependency_map=dependency_map,
        )

    @staticmethod
    def _base_selectors() -> list[ContextSelector]:
        return [
            FarmSelector(),
            UserSettingsSelector(),
            CycleSelector(),
            TaskStateSelector(),
            MemorySelector(),
            ConversationSelector(),
        ]

    def _apply_dependency_selectors(
        self,
        selectors: list[ContextSelector],
        request: ContextBuildRequest,
    ) -> dict[str, list[str]]:
        dependency_map: dict[str, list[str]] = {}
        for dependency in self._dependencies_from_request(request):
            selector_spec = self.DEPENDENCY_SELECTORS.get(dependency)
            if selector_spec is None:
                continue
            selector_cls, block_key = selector_spec
            self._append_selector_once(selectors, selector_cls)
            dependency_map.setdefault(block_key, []).append(dependency)
        return dependency_map

    def _apply_tool_selectors(
        self,
        selectors: list[ContextSelector],
        layers: list[ContextLayer],
        selected_tool_names: set[str],
    ) -> int:
        max_tokens = 512
        if selected_tool_names & self.COST_TOOLS:
            self._append_selector_once(selectors, LedgerSelector)
            layers.append(ContextLayer.RETRIEVAL)
            max_tokens = max(max_tokens, 900)
        if selected_tool_names & self.CROP_CYCLE_TOOLS:
            max_tokens = max(max_tokens, 700)
        if selected_tool_names & self.WEATHER_TOOLS:
            self._append_selector_once(selectors, WeatherSelector)
            self._append_selector_once(selectors, RetrievalSelector)
            layers.append(ContextLayer.RETRIEVAL)
        return max_tokens

    def _apply_retrieval_selectors(
        self,
        selectors: list[ContextSelector],
        layers: list[ContextLayer],
        request: ContextBuildRequest,
        max_tokens: int,
    ) -> int:
        if request.include_retrieval:
            self._append_selector_once(selectors, RetrievalSelector)
            layers.append(ContextLayer.RETRIEVAL)
        if self._should_trigger_rag(request):
            self._append_selector_once(selectors, KnowledgeSelector)
            layers.append(ContextLayer.RETRIEVAL)
            max_tokens = max(max_tokens, 900)
        return max_tokens

    @staticmethod
    def _append_selector_once(
        selectors: list[ContextSelector],
        selector_cls: type,
    ) -> None:
        if not any(isinstance(selector, selector_cls) for selector in selectors):
            selectors.append(selector_cls())

    def _should_trigger_rag(self, request: ContextBuildRequest) -> bool:
        if not self.rag_enabled:
            return False
        intent = request.intent.lower()
        query = request.query.strip()
        if any(hint in intent for hint in self.RAG_BLOCKED_INTENT_HINTS):
            return False
        if any(hint in query for hint in self.RAG_BLOCKED_QUERY_HINTS):
            return False
        if any(hint in intent for hint in self.RAG_INTENT_HINTS):
            return True
        return bool(query) and any(hint in query for hint in self.RAG_QUERY_HINTS)

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

        if selected_tool_names & self.COST_TOOLS:
            add(["farm", "crop_cycle", "ledger"])
        if selected_tool_names & self.CROP_CYCLE_TOOLS:
            add(["crop_cycle"])
        if selected_tool_names & self.WORK_ORDER_TOOLS:
            add(["crop_cycle", "planting_units", "operation_work_orders", "workers"])
        if selected_tool_names & self.LABOR_TOOLS:
            add(["workers", "unpaid_labor", "ledger"])
        if selected_tool_names & self.COST_CATEGORY_TOOLS:
            add(["ledger", "cost_categories"])
        if selected_tool_names & self.PLANTING_UNIT_TOOLS:
            add(["farm", "crop_cycles", "planting_units"])
        if selected_tool_names & self.WEATHER_TOOLS:
            add(["weather"])
        return dependencies


__all__ = [
    "ContextBuildRequest",
    "ContextLayer",
    "ContextPolicy",
    "ContextPolicyResult",
    "ContextSelector",
]
