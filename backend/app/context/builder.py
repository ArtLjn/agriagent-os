"""Context Builder — Agent 入模上下文的唯一入口。

其他模块只通过 ``ContextBuilder`` 构建 Context，不再有 ContextEngine / Legacy 等并行入口。

目录导航
--------
``app/context/`` 以少数稳定入口组织，避免为单个小文件创建目录：

- ``builder.py``         本文件，对外唯一入口（``ContextBuilder``）
- ``pipeline.py``        预算 / 压缩 / 白名单 / 渲染 / trace 安全文本工具
- ``knowledge.py``       ``RAGKnowledgeProvider`` / ``RAGUnavailableError``
- ``task_state.py``      ``AgentTaskState`` / ``AgentTaskStateStore``
- ``sources.py``         selector 分组、默认顺序与 dependency 映射 catalog

- ``core/``              核心数据契约
  - ``models.py``        ``ContextBlock`` / ``ContextBundle`` / ``estimate_tokens``
  - ``policy.py``        ``ContextPolicy`` / ``ContextBuildRequest`` / ``ContextPolicyResult`` / ``ContextLayer``
  - ``document.py``      ``ContextDocument`` / ``ContextSection``（prompt 文档结构）
  - ``registry.py``      Block 注册表与 ``ContextBlockSpec`` / ``ContextCategory``

- ``runtime/``           运行时辅助（缓存 / 预热 / 失效 / trace）
  - ``cache.py``         ContextBundle 缓存
  - ``preload.py``       并行预热 selector / tool 缓存
  - ``invalidation.py``  ``invalidate_farm_context``，写操作后失效缓存
  - ``trace.py``         构建 trace payload，供可观测平台消费

- ``selectors/``         各业务域 selector（Farm / Cycle / Weather / Memory ...）
"""

from __future__ import annotations

from dataclasses import asdict
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.context.core.models import ContextBlock, ContextBundle
from app.context.core.policy import ContextPolicy
from app.context.knowledge import RAGUnavailableError
from app.context.pipeline import is_allowed_key
from app.context.pipeline import TokenBudget
from app.context.runtime import build_context_trace_payload
from app.context.sources import (
    CycleSelector,
    build_default_context_selectors,
)
from app.domains.farm.models import Farm
from app.domains.users.models import User
from app.domains.users.settings_models import UserSetting
from app.infra.trace_collector import get_collector
from app.shared.config import (
    DEFAULT_ASSISTANT_ROLE,
    assistant_role_prompt,
    normalize_assistant_role,
)

if TYPE_CHECKING:
    from app.context.core.policy import ContextBuildRequest, ContextSelector
    from app.memory.models import MemoryContext


class ContextBuilder:
    """Agent 入模 Context 的构建入口。

    使用方式::

        builder = ContextBuilder(max_tokens=1200, policy=ContextPolicy())
        bundle = builder.build_runtime_context_bundle(db, request, memory_context)

    或在不需要策略推导时直接调用::

        bundle = builder.build(db=db, farm_id=farm_id, user_id=user_id)
    """

    def __init__(
        self,
        selectors: list[ContextSelector] | None = None,
        max_tokens: int = 1200,
        policy: ContextPolicy | None = None,
        trace_collector: Any | None = None,
    ) -> None:
        self.selectors = selectors or default_context_selectors()
        self.policy = policy
        self.budget = TokenBudget(max_tokens=max_tokens)
        self.trace_collector = trace_collector

    # ----- 主流程 -------------------------------------------------------------

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
        blocks, selector_errors, selector_metadata = self._select_blocks(
            db=db,
            farm_id=farm_id,
            user_id=user_id,
            session_id=session_id,
            **kwargs,
        )

        original_keys = {block.key for block in blocks}
        blocks = self._apply_allowlist_filter(blocks)
        filtered_keys = original_keys - {block.key for block in blocks}

        bundle = self.budget.apply(blocks)
        bundle.metadata["selector_errors"] = selector_errors
        bundle.metadata["selector_metadata"] = selector_metadata
        bundle.metadata["allowlist_filtered_keys"] = sorted(filtered_keys)
        policy_trace = kwargs.get("policy_trace")
        if isinstance(policy_trace, dict):
            bundle.metadata["policy"] = policy_trace
        self._attach_dependency_summary(
            bundle,
            kwargs.get("context_dependency_map") or {},
        )
        self._record_trace(bundle, start)
        return bundle

    def build_runtime_context_bundle(
        self,
        db: Session,
        request: ContextBuildRequest,
        memory_context: MemoryContext | None = None,
        context_pack: Any | None = None,
    ) -> ContextBundle:
        """按策略构建 Runtime ContextBundle。"""
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
                context_pack=context_pack,
                context_dependency_map=policy_result.dependency_map,
                policy_trace={
                    "intent": request.intent,
                    "selected_tool_names": list(request.selected_tool_names),
                    "enabled_layers": sorted(
                        layer.value for layer in policy_result.enabled_layers
                    ),
                    "context_dependency_map": policy_result.dependency_map,
                },
                query=request.query,
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
        _attach_context_pack_metadata(bundle, context_pack)
        return bundle

    def build_farm_runtime_context(self, db: Session, farm_id: int) -> dict:
        """返回 Agent Runtime 仍需要的农场扁平字典。

        字段：farm_location / farm_coords / display_name / active_crops /
        assistant_role / assistant_role_prompt。
        Runtime 完成迁移到 ContextBundle 后该方法可移除。
        """
        return _build_farm_runtime_context_dict(db=db, farm_id=farm_id)

    # ----- 内部步骤 -----------------------------------------------------------

    def _select_blocks(
        self,
        *,
        db: Session,
        farm_id: int,
        user_id: str | None,
        session_id: str | None,
        **kwargs,
    ) -> tuple[list[ContextBlock], list[dict[str, str]], dict[str, dict]]:
        blocks: list[ContextBlock] = []
        selector_errors: list[dict[str, str]] = []
        selector_metadata: dict[str, dict] = {}
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
                self._collect_selector_metadata(selector_metadata, selector)
            except RAGUnavailableError:
                raise
            except Exception as exc:
                selector_errors.append(
                    {
                        "selector": selector.__class__.__name__,
                        "error": str(exc)[:200],
                    }
                )
        return blocks, selector_errors, selector_metadata

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
        """按白名单过滤 blocks，违禁字段不进入 prompt。"""
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

    @staticmethod
    def _collect_selector_metadata(
        selector_metadata: dict[str, dict],
        selector,
    ) -> None:
        metadata = getattr(selector, "last_metadata", None)
        if not isinstance(metadata, dict) or not metadata:
            return
        if "rag_called" in metadata:
            selector_metadata["knowledge"] = dict(metadata)

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
                input_data=self._trace_input_data(bundle),
                output_data=build_context_trace_payload(bundle),
                start_time=start,
                duration_ms=int((time.time() - start) * 1000),
                token_usage={"context_tokens": bundle.token_estimate},
            )
        except Exception:
            return

    @staticmethod
    def _trace_input_data(bundle: ContextBundle) -> dict[str, Any]:
        policy = bundle.metadata.get("policy")
        input_data: dict[str, Any] = {
            "block_count": len(bundle.blocks),
            "selected_keys": [block.key for block in bundle.blocks],
        }
        if isinstance(policy, dict) and policy.get("intent"):
            input_data["policy_intent"] = policy["intent"]
        return input_data


def default_context_selectors() -> list[ContextSelector]:
    """返回 ContextBuilder 的默认 selector 顺序。"""
    return build_default_context_selectors()


def _build_farm_runtime_context_dict(db: Session, farm_id: int) -> dict:
    """组装 Agent Runtime 仍消费的农场扁平字典。

    Runtime 还未完全切换到 ContextBundle，依然读取 farm_location /
    farm_coords / display_name / active_crops / assistant_role 等扁平字段，
    这里集中生产，避免散落到调用方。
    """
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
            db.query(UserSetting).filter(UserSetting.user_id == farm.user_id).first()
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


def _attach_context_pack_metadata(
    bundle: ContextBundle,
    context_pack: Any | None,
) -> None:
    if context_pack is None:
        return
    diagnostics = getattr(context_pack, "diagnostics", None)
    if diagnostics is None:
        return
    bundle.metadata["context_pack"] = asdict(diagnostics)


__all__ = ["ContextBuilder", "default_context_selectors"]
