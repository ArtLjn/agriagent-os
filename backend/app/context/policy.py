"""Context 构建策略入口。"""

from dataclasses import dataclass, field
from typing import Protocol

from app.core.compat import StrEnum
from app.context.models import ContextBlock
from app.context.selectors import (
    ConversationSelector,
    CycleSelector,
    FarmSelector,
    LedgerSelector,
    MemorySelector,
    RetrievalSelector,
    UserSettingsSelector,
    WeatherSelector,
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


class ContextPolicy:
    """根据意图和工具选择 Context 构建策略。"""

    COST_TOOLS = frozenset({"get_cost_summary"})
    WEATHER_TOOLS = frozenset({"get_weather_forecast"})

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

        if selected_tool_names & self.COST_TOOLS:
            selectors.append(LedgerSelector())
            layers.append(ContextLayer.RETRIEVAL)
            max_tokens = max(max_tokens, 900)

        if selected_tool_names & self.WEATHER_TOOLS:
            selectors.append(WeatherSelector())
            selectors.append(RetrievalSelector())
            layers.append(ContextLayer.RETRIEVAL)

        if request.include_retrieval:
            selectors.append(RetrievalSelector())
            layers.append(ContextLayer.RETRIEVAL)

        return ContextPolicyResult(
            enabled_layers=list(dict.fromkeys(layers)),
            selectors=selectors,
            max_tokens=max_tokens,
        )


__all__ = [
    "ContextBuildRequest",
    "ContextLayer",
    "ContextPolicy",
    "ContextPolicyResult",
]
