"""ContextBuilder 兼容门面。

新代码应直接使用 app.context.engine.ContextEngine。
"""

from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.context.engine import ContextEngine

if TYPE_CHECKING:
    from app.context.models import ContextBundle
    from app.context.policy import ContextBuildRequest, ContextPolicy, ContextSelector
    from app.memory.models import MemoryContext


class ContextBuilder:
    """兼容旧 API 的 Context 构建入口。"""

    def __init__(
        self,
        selectors: list["ContextSelector"] | None = None,
        max_tokens: int = 1200,
        policy: "ContextPolicy | None" = None,
        trace_collector: Any | None = None,
    ) -> None:
        self._engine = ContextEngine(
            selectors=selectors,
            max_tokens=max_tokens,
            policy=policy,
            trace_collector=trace_collector,
        )

    def build(
        self,
        db: Session,
        farm_id: int,
        user_id: str | None = None,
        session_id: str | None = None,
        **kwargs,
    ) -> "ContextBundle":
        """兼容旧 build() API，委托 ContextEngine。"""
        return self._engine.build(
            db=db,
            farm_id=farm_id,
            user_id=user_id,
            session_id=session_id,
            **kwargs,
        )

    def build_runtime_context_bundle(
        self,
        db: Session,
        request: "ContextBuildRequest",
        memory_context: "MemoryContext | None" = None,
    ) -> "ContextBundle":
        """兼容旧 Runtime ContextBundle API，委托 ContextEngine。"""
        return self._engine.build_runtime_context_bundle(
            db=db,
            request=request,
            memory_context=memory_context,
        )

    def build_farm_runtime_context(self, db: Session, farm_id: int) -> dict:
        """兼容 Agent Runtime 的旧 farm context 字典形状。"""
        return self._engine.build_farm_runtime_context(db=db, farm_id=farm_id)


__all__ = ["ContextBuilder"]
