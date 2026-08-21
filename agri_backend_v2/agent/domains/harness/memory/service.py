"""Memory Service 兼容门面。

具体职责按设计拆分到：

* ``models.py``：Memory 边界契约和租户范围；
* ``short_term.py``：Session View、Short Memory 和 Conversation state；
* ``long_term.py``：Long-term Memory observation/search 端口；
* ``policy.py``：Short/Long Memory Context 注入决策。

现有 Runtime、Worker、API 和测试继续通过本模块访问，后续可按调用方边界
逐步切换到子模块，而不把存储实现泄漏到 Runtime。
"""

from __future__ import annotations

from agent.domains.harness.memory.long_term import observe, search
from agent.domains.harness.memory.models import (
    MemoryHit,
    MemoryHitStatus,
    MemoryObservation,
    MemoryScope,
    MemorySearchResult,
    ObservationStatus,
    SessionView,
    SourceStatus,
)
from agent.domains.harness.memory.policy import (
    MemoryInjectionPolicy,
    resolve_memory_policy,
)
from agent.domains.harness.memory.short_term import (
    complete_turns,
    empty_session_view,
    get_session_view,
    persist_session_turn,
    prepare_pending_action,
    prepare_task_state,
    project_recent_turns,
    reset_session,
    source_divergence,
)


__all__ = [
    "MemoryHit",
    "MemoryHitStatus",
    "MemoryInjectionPolicy",
    "MemoryObservation",
    "MemoryScope",
    "MemorySearchResult",
    "ObservationStatus",
    "SessionView",
    "SourceStatus",
    "complete_turns",
    "empty_session_view",
    "get_session_view",
    "observe",
    "persist_session_turn",
    "prepare_pending_action",
    "prepare_task_state",
    "project_recent_turns",
    "reset_session",
    "resolve_memory_policy",
    "search",
    "source_divergence",
]
