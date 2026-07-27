"""Context 工程模块。

入口
----
外部代码统一通过 ``ContextBuilder`` 构建 Context：

    from app.context import ContextBuilder

子模块分工见 ``app/context/builder.py`` 顶部文档。
"""

from app.context.builder import ContextBuilder, default_context_selectors
from app.context.budget import TokenBudget
from app.context.document import ContextDocument, ContextSection
from app.context.models import ContextBlock, ContextBundle, estimate_tokens
from app.context.policy import (
    ContextBuildRequest,
    ContextLayer,
    ContextPolicy,
    ContextPolicyResult,
)
from app.context.renderer import ContextRenderer

__all__ = [
    "ContextBlock",
    "ContextBuildRequest",
    "ContextBuilder",
    "ContextBundle",
    "ContextDocument",
    "ContextLayer",
    "ContextPolicy",
    "ContextPolicyResult",
    "ContextRenderer",
    "ContextSection",
    "TokenBudget",
    "default_context_selectors",
    "estimate_tokens",
]
