"""Context Builder。"""

import time
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy.orm import Session

from app.context.budget import TokenBudget
from app.context.models import ContextBlock, ContextBundle
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
from app.infra.trace_collector import get_collector
from app.models.farm import Farm
from app.models.user import User
from app.models.user_setting import UserSetting

if TYPE_CHECKING:
    from app.context.policy import ContextBuildRequest, ContextPolicy
    from app.memory.models import MemoryContext


class ContextSelector(Protocol):
    """Context selector 协议。"""

    def select(self, **kwargs) -> list[ContextBlock]: ...


class ContextBuilder:
    """构建 Agent 输入上下文。"""

    def __init__(
        self,
        selectors: list[ContextSelector] | None = None,
        max_tokens: int = 1200,
        policy: "ContextPolicy | None" = None,
        trace_collector: Any | None = None,
    ) -> None:
        self.selectors = selectors or [
            FarmSelector(),
            CycleSelector(),
            UserSettingsSelector(),
            LedgerSelector(),
            WeatherSelector(),
            ConversationSelector(),
            MemorySelector(),
            RetrievalSelector(),
        ]
        self.policy = policy
        self.budget = TokenBudget(max_tokens=max_tokens)
        self.trace_collector = trace_collector

    def build(
        self,
        db: Session,
        farm_id: int,
        user_id: str | None = None,
        session_id: str | None = None,
        **kwargs,
    ) -> ContextBundle:
        """选择上下文、应用预算并记录 trace。"""
        start = time.time()
        blocks: list[ContextBlock] = []
        selector_errors: list[dict[str, str]] = []
        for selector in self.selectors:
            try:
                blocks.extend(
                    selector.select(
                        db=db,
                        farm_id=farm_id,
                        user_id=user_id,
                        session_id=session_id,
                        **kwargs,
                    )
                )
            except Exception as exc:
                selector_errors.append(
                    {
                        "selector": selector.__class__.__name__,
                        "error": str(exc)[:200],
                    }
                )

        bundle = self.budget.apply(blocks)
        bundle.metadata["selector_errors"] = selector_errors
        self._record_trace(bundle, start)
        return bundle

    def build_runtime_context_bundle(
        self,
        db: Session,
        request: "ContextBuildRequest",
        memory_context: "MemoryContext | None" = None,
    ) -> ContextBundle:
        """按策略构建 Runtime ContextBundle。"""
        from app.context.policy import ContextPolicy

        policy = self.policy or ContextPolicy()
        policy_result = policy.resolve(request)
        previous_selectors = self.selectors
        previous_budget = self.budget

        try:
            self.selectors = policy_result.selectors
            self.budget = TokenBudget(max_tokens=policy_result.max_tokens)
            bundle = self.build(
                db=db,
                farm_id=request.farm_id,
                user_id=request.user_id,
                session_id=request.session_id,
                memory_context=memory_context,
            )
        finally:
            self.selectors = previous_selectors
            self.budget = previous_budget

        bundle.metadata["policy"] = {
            "intent": request.intent,
            "selected_tool_names": list(request.selected_tool_names),
            "enabled_layers": sorted(
                layer.value for layer in policy_result.enabled_layers
            ),
        }
        return bundle

    def build_farm_runtime_context(self, db: Session, farm_id: int) -> dict:
        """兼容 Agent Runtime 的旧 farm context 字典形状。"""
        farm = db.query(Farm).filter(Farm.id == farm_id).first()
        display_name = "农友"
        user_city = ""
        user_lat = None
        user_lon = None
        active_crops = ""

        if farm and farm.user_id:
            user = db.query(User).filter(User.id == farm.user_id).first()
            if user and user.nickname:
                display_name = user.nickname
            setting = (
                db.query(UserSetting)
                .filter(UserSetting.user_id == farm.user_id)
                .first()
            )
            if setting:
                user_city = setting.default_city or ""
                user_lat = setting.default_lat
                user_lon = setting.default_lon

            cycle_block = CycleSelector().select(db=db, farm_id=farm_id)[0]
            active_crops = (
                cycle_block.content.removeprefix("活跃茬口：")
                if "活跃茬口：" in cycle_block.content
                else ""
            )

        farm_location = user_city or (farm.location if farm and farm.location else "")
        farm_coords = ""
        if user_lat is not None and user_lon is not None:
            farm_coords = f"{user_lat:.4f},{user_lon:.4f}"

        return {
            "farm_location": farm_location,
            "farm_coords": farm_coords,
            "display_name": display_name,
            "active_crops": active_crops,
        }

    def _record_trace(self, bundle: ContextBundle, start: float) -> None:
        collector = self.trace_collector
        if collector is None:
            try:
                collector = get_collector()
            except Exception:
                return
        try:
            collector.record(
                node_type="context_build",
                node_name="context_bundle",
                input_data={"block_count": len(bundle.blocks)},
                output_data=bundle.summary(),
                start_time=start,
                duration_ms=int((time.time() - start) * 1000),
                token_usage={"context_tokens": bundle.token_estimate},
            )
        except Exception:
            return


__all__ = ["ContextBuilder", "ContextSelector"]
