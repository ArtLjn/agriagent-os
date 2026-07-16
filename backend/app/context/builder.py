"""Context Builder。"""

import time
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.agent.assistant_roles import (
    DEFAULT_ASSISTANT_ROLE,
    assistant_role_prompt,
    normalize_assistant_role,
)
from app.context.allowlist import is_allowed_key
from app.context.budget import TokenBudget
from app.context.models import ContextBlock, ContextBundle
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
from app.infra.trace_collector import get_collector
from app.models.farm import Farm
from app.models.user import User
from app.models.user_setting import UserSetting

if TYPE_CHECKING:
    from app.context.policy import ContextBuildRequest, ContextPolicy, ContextSelector
    from app.memory.models import MemoryContext


class ContextBuilder:
    """构建 Agent 输入上下文。"""

    def __init__(
        self,
        selectors: list["ContextSelector"] | None = None,
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
            PlantingUnitSelector(),
            OperationWorkOrderSelector(),
            WorkerSelector(),
            UnpaidLaborSummarySelector(),
            CostCategorySelector(),
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
                selected_blocks = selector.select(
                    db=db,
                    farm_id=farm_id,
                    user_id=user_id,
                    session_id=session_id,
                    **kwargs,
                )
                blocks.extend(
                    self._apply_dependency_metadata(
                        selected_blocks,
                        kwargs.get("context_dependency_map") or {},
                    )
                )
            except Exception as exc:
                selector_errors.append(
                    {
                        "selector": selector.__class__.__name__,
                        "error": str(exc)[:200],
                    }
                )

        # 白名单过滤：违禁字段不进入 prompt（设计意图见 13_Agent范式规范化设计.md §5.9.2）
        original_keys = {b.key for b in blocks}
        blocks = self._apply_allowlist_filter(blocks)
        filtered_keys = original_keys - {b.key for b in blocks}

        bundle = self.budget.apply(blocks)
        bundle.metadata["selector_errors"] = selector_errors
        bundle.metadata["allowlist_filtered_keys"] = sorted(filtered_keys)
        self._attach_dependency_summary(
            bundle,
            kwargs.get("context_dependency_map") or {},
        )
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
                context_dependency_map=policy_result.dependency_map,
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
            "context_dependency_map": policy_result.dependency_map,
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
        assistant_role = DEFAULT_ASSISTANT_ROLE

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
                assistant_role = normalize_assistant_role(setting.assistant_role)

            cycle_block = CycleSelector().select(db=db, farm_id=farm_id)[0]
            active_crops = (
                cycle_block.content.removeprefix("活跃茬口：")
                if "活跃茬口：" in cycle_block.content
                else ""
            )

        farm_location = user_city or (farm.location if farm and farm.location else "")
        farm_coords = ""
        if isinstance(user_lat, int | float) and isinstance(user_lon, int | float):
            farm_coords = f"{user_lat:.4f},{user_lon:.4f}"

        return {
            "farm_location": farm_location,
            "farm_coords": farm_coords,
            "display_name": display_name,
            "active_crops": active_crops,
            "assistant_role": assistant_role,
            "assistant_role_prompt": assistant_role_prompt(assistant_role),
        }

    @staticmethod
    def _apply_dependency_metadata(
        blocks: list[ContextBlock],
        dependency_map: dict[str, list[str]],
    ) -> list[ContextBlock]:
        if not dependency_map:
            return blocks
        annotated = []
        for block in blocks:
            dependencies = dependency_map.get(block.key, [])
            if dependencies:
                annotated.append(
                    block.with_metadata(
                        selected_by_skill_dependencies=sorted(set(dependencies)),
                        required_reason="skill_metadata_dependency",
                    )
                )
            else:
                annotated.append(block)
        return annotated

    @staticmethod
    def _apply_allowlist_filter(
        blocks: list[ContextBlock],
    ) -> list[ContextBlock]:
        """按白名单过滤 blocks，违禁字段不进入 prompt。

        设计意图见 13_Agent范式规范化设计.md §5.9.2。
        未在白名单中的 key 视为违禁，过滤掉。
        """
        return [block for block in blocks if is_allowed_key(block.key)]

    @staticmethod
    def _attach_dependency_summary(
        bundle: ContextBundle,
        dependency_map: dict[str, list[str]],
    ) -> None:
        if not dependency_map:
            bundle.metadata["context_dependency_diagnostics"] = []
            return
        selected_keys = {block.key for block in bundle.blocks}
        compressed_keys = {block.key for block in bundle.compressed_blocks}
        dropped_keys = {block.key for block in bundle.dropped_blocks}
        diagnostics = []
        for block_key, dependencies in sorted(dependency_map.items()):
            if block_key in dropped_keys:
                status = "dropped"
            elif block_key in compressed_keys:
                status = "compressed"
            elif block_key in selected_keys:
                status = "selected"
            else:
                status = "unavailable"
            diagnostics.append(
                {
                    "block_key": block_key,
                    "dependencies": sorted(set(dependencies)),
                    "status": status,
                }
            )
        bundle.metadata["context_dependency_diagnostics"] = diagnostics

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


__all__ = ["ContextBuilder"]
