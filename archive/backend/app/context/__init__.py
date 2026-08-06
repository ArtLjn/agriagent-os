"""Context 工程模块。

入口
----
外部代码统一通过 ``ContextBuilder`` 构建 Context：

    from app.context import ContextBuilder

子模块分工见 ``app/context/builder.py`` 顶部文档。
"""

from app.context.builder import ContextBuilder, default_context_selectors
from app.context.pipeline import TokenBudget
from app.context.core.document import ContextDocument, ContextSection
from app.context.core.models import ContextBlock, ContextBundle, estimate_tokens
from app.context.core.policy import (
    ContextBuildRequest,
    ContextLayer,
    ContextPolicy,
    ContextPolicyResult,
)
from app.context.pack import (
    ContextPack,
    ContextPackDiagnostics,
    ContextPackService,
    ConversationSummaryBlock,
    MessageSnapshot,
)
from app.context.pipeline import ContextRenderer

__all__ = [
    "ContextBlock",
    "ContextBuildRequest",
    "ContextBuilder",
    "ContextBundle",
    "ContextDocument",
    "ContextLayer",
    "ContextPack",
    "ContextPackDiagnostics",
    "ContextPackService",
    "ContextPolicy",
    "ContextPolicyResult",
    "ContextRenderer",
    "ContextSection",
    "ConversationSummaryBlock",
    "MessageSnapshot",
    "TokenBudget",
    "default_context_selectors",
    "estimate_tokens",
]
