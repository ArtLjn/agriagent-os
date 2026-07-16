# Backend Directory Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strictly execute the remaining backend bloat and directory redesign work from `docs/specs/2026-07-12-backend-bloat-diagnosis.md` and `docs/specs/2026-07-14-backend-directory-redesign.md` as small, reviewable PRs.

**Architecture:** Work proceeds in isolated worktrees, one PR per migration step. P0/P1 reduce duplication and dead abstractions first; only after those pass do P1 structural migrations create `application/` and `skills/`, followed by P2 `platforms/` migration and repository backend cleanup. Completed P0-1/P0-2 are treated as baseline and are not reimplemented.

**Tech Stack:** FastAPI backend, Python 3.11, SQLAlchemy, pytest, ruff, GitHub PR workflow, existing project scripts under `scripts/`.

---

## Source Of Truth

This plan is derived only from:

- `docs/specs/2026-07-12-backend-bloat-diagnosis.md`
- `docs/specs/2026-07-14-backend-directory-redesign.md`

Completed baseline:

- P0-1 / B1: `backend/app/agent/planner/` has no tracked files and no code references.
- P0-2 / B2: `backend/app/agent/planning/` has been migrated to `backend/app/agent/runtime/planning/`.

Current non-code local state:

- `backend/config.yaml` is ignored and must not be committed.
- `backend/var/`, `bug.txt`, and `data/` are local untracked items and must not be touched by remediation PRs.

## Dispatch Rules

Every worktree task must:

1. Start from `origin/main` in repository `ArtLjn/agriagent-os`.
2. Use branch prefix `codex/`.
3. Touch only files listed in that task.
4. Run the task-specific tests.
5. Run:
   ```bash
   ruff check backend/app backend/tests
   bash scripts/check-complexity-budget.sh
   ```
6. If `scripts/check-complexity-budget.sh` fails because pytest generated `__pycache__` or `*.pyc`, clean generated Python artifacts and rerun:
   ```bash
   find backend -type d -name __pycache__ -prune -exec rm -rf {} +
   find backend -type f -name '*.pyc' -delete
   bash scripts/check-complexity-budget.sh
   ```
7. Update both source specs when the task changes a tracked status row:
   - `docs/specs/2026-07-12-backend-bloat-diagnosis.md`
   - `docs/specs/2026-07-14-backend-directory-redesign.md`
8. Open a PR, wait for review, then merge if mergeable.

## Execution Queue

| Order | Spec ID | Worktree task | PR boundary |
| --- | --- | --- | --- |
| 1 | P0-3 | Merge duplicate `ContextSelector` Protocol | Low-risk type cleanup |
| 2 | P0-4 | Merge runtime top fragments | Runtime micro-file cleanup |
| 3 | P0-5 | Merge `observability/` package | Observability micro-package cleanup |
| 4 | P0-6 | Merge `agent/application` three helper fragments | Chat helper cleanup |
| 5 | P1-1 | Remove `MemoryServicePort` | Single-implementation Protocol cleanup |
| 6 | P1-2 | Remove `_ComparableStage(Protocol)` | Private Protocol cleanup |
| 7 | P1-3 | Evaluate and remove `core/compat.py` if Python baseline allows | Compatibility cleanup |
| 8 | D0 | Add `app.agent.application` compatibility layer for future migration | Structural migration guard |
| 9 | C0 | Add `app.agent.skills` compatibility layer for future migration | Structural migration guard |
| 10 | D1-D2 | Move `agent/application` to `app/application` with compatibility intact | Application layer extraction |
| 11 | C1-C3 | Move `agent/skills` to `app/skills` with compatibility intact | Skills layer extraction |
| 12 | B3 | Move agent root business files to target packages | Agent slimming |
| 13 | E1-E4 | Replace LangGraph with pure Python runtime loop | Runtime simplification |
| 14 | P2-1/A1-A3 | Extract `platforms/shared` prerequisites | Shared platform boundary |
| 15 | P2-3/P2-4 | Confirm and reduce unused document repository backends | Repository backend cleanup |
| 16 | A4-A6 | Move `evaluation/` and `data_flywheel/` into `platforms/` | Platform extraction |
| 17 | P2-4/P2-6 | Tests root reorganization and empty directory cleanup | Repository hygiene |
| 18 | P3 | CI sensors for Protocol/backend-proof rules | Long-term governance |

---

### Task 1: P0-3 Merge Duplicate `ContextSelector`

**Files:**
- Modify: `backend/app/context/policy.py`
- Modify: `backend/app/context/builder.py`
- Test: `backend/tests/context/test_context_selector_protocol.py`
- Modify docs: both source specs

- [ ] **Step 1: Add a focused regression test**

Create `backend/tests/context/test_context_selector_protocol.py`:

```python
"""ContextSelector Protocol single-source tests."""

import pytest

from app.context.builder import ContextBuilder
from app.context.policy import ContextBuildRequest, ContextPolicy, ContextSelector

pytestmark = pytest.mark.no_db


def test_context_builder_uses_policy_context_selector_protocol() -> None:
    builder_annotations = ContextBuilder.__init__.__annotations__

    assert "selectors" in builder_annotations
    assert "ContextSelector" in str(builder_annotations["selectors"])
    assert ContextSelector.__module__ == "app.context.policy"


def test_context_policy_still_resolves_default_selectors() -> None:
    result = ContextPolicy().resolve(ContextBuildRequest(farm_id=1))

    assert result.selectors
    assert result.max_tokens >= 512
```

- [ ] **Step 2: Verify the test fails before implementation**

Run:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/context/test_context_selector_protocol.py -q
```

Expected: FAIL because `builder.py` still defines a second `ContextSelector`.

- [ ] **Step 3: Remove the duplicate Protocol**

In `backend/app/context/builder.py`, replace:

```python
from typing import TYPE_CHECKING, Any, Protocol
```

with:

```python
from typing import TYPE_CHECKING, Any
```

and remove:

```python
class ContextSelector(Protocol):
    """Context selector 协议。"""

    def select(self, **kwargs) -> list[ContextBlock]: ...
```

Inside the `TYPE_CHECKING` block, import the canonical Protocol:

```python
if TYPE_CHECKING:
    from app.context.policy import ContextBuildRequest, ContextPolicy, ContextSelector
    from app.memory.models import MemoryContext
```

Keep the constructor annotation as:

```python
selectors: list["ContextSelector"] | None = None,
```

- [ ] **Step 4: Run task tests**

Run:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/context/test_context_selector_protocol.py tests/agent/test_chat_use_case.py -q
```

Expected: PASS.

- [ ] **Step 5: Update docs**

In both source specs, mark P0-3 as completed with commit placeholder `本工作树待提交` and verification:

```text
`ContextSelector` 仅保留 `app.context.policy.ContextSelector`；builder 只在 TYPE_CHECKING 下引用；context selector regression 通过。
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/context/builder.py backend/tests/context/test_context_selector_protocol.py \
  docs/specs/2026-07-12-backend-bloat-diagnosis.md \
  docs/specs/2026-07-14-backend-directory-redesign.md
git commit -m "refactor: 合并 ContextSelector 协议定义"
```

---

### Task 2: P0-4 Merge Runtime Top Fragments

**Files:**
- Create: `backend/app/agent/runtime/support.py`
- Modify: `backend/app/agent/runtime/nodes.py`
- Modify imports currently using `runtime.errors`, `runtime.quota`, or `runtime.graph_factory`
- Delete: `backend/app/agent/runtime/errors.py`
- Delete: `backend/app/agent/runtime/quota.py`
- Delete: `backend/app/agent/runtime/graph_factory.py`
- Test: `backend/tests/agent/runtime/test_runtime_support.py`
- Modify docs: both source specs

- [ ] **Step 1: Add support module tests**

Create `backend/tests/agent/runtime/test_runtime_support.py`:

```python
"""Agent runtime support module tests."""

import pytest

from app.agent.runtime.support import (
    AgentRuntimeError,
    QUOTA_REJECT_MESSAGES,
    compile_advisor_graph,
)

pytestmark = pytest.mark.no_db


def test_runtime_support_exports_runtime_error_and_quota_messages() -> None:
    assert issubclass(AgentRuntimeError, RuntimeError)
    assert QUOTA_REJECT_MESSAGES["identity"] == "缺少可信用户上下文，无法继续处理。"


def test_runtime_support_exports_graph_compiler() -> None:
    assert callable(compile_advisor_graph)
```

- [ ] **Step 2: Verify test fails before implementation**

Run:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/runtime/test_runtime_support.py -q
```

Expected: FAIL because `app.agent.runtime.support` does not exist.

- [ ] **Step 3: Create `support.py`**

Create `backend/app/agent/runtime/support.py`:

```python
"""Agent runtime shared support primitives."""

from langgraph.graph import END, StateGraph

from app.agent.state import AgentState
from app.core.database import SessionLocal
from app.services.quota_service import QuotaCheckResult, check_user_quota


class AgentRuntimeError(RuntimeError):
    """Agent Runtime 基础错误。"""


QUOTA_REJECT_MESSAGES = {
    "month": "本月用量已达上限，配额将在下月重置。",
    "week": "本周用量已达上限，配额将在下周一重置。",
    "identity": "缺少可信用户上下文，无法继续处理。",
}


def check_quota(user_id: str | None) -> QuotaCheckResult:
    db = SessionLocal()
    try:
        return check_user_quota(user_id, db)
    finally:
        db.close()


def compile_advisor_graph():
    """编译建议 Agent 的 StateGraph（支持并行 Skill 执行，最大 15 步）。"""
    from app.agent.runtime.nodes import _llm_node, _parallel_tool_node, _should_continue

    graph = StateGraph(AgentState)
    graph.add_node("llm", _llm_node)
    graph.add_node("tools", _parallel_tool_node)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", _should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")
    return graph.compile()


__all__ = [
    "AgentRuntimeError",
    "QUOTA_REJECT_MESSAGES",
    "check_quota",
    "compile_advisor_graph",
]
```

- [ ] **Step 4: Update imports**

Replace:

```python
from app.agent.runtime.quota import QUOTA_REJECT_MESSAGES, check_quota
```

with:

```python
from app.agent.runtime.support import QUOTA_REJECT_MESSAGES, check_quota
```

Replace any `app.agent.runtime.graph_factory` import with `app.agent.runtime.support`.
Replace any `app.agent.runtime.errors` import with `app.agent.runtime.support`.

- [ ] **Step 5: Delete the three source fragments**

```bash
git rm backend/app/agent/runtime/errors.py \
  backend/app/agent/runtime/quota.py \
  backend/app/agent/runtime/graph_factory.py
```

- [ ] **Step 6: Run task tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/runtime/test_runtime_support.py tests/agent/test_chat_use_case.py -q
```

Expected: PASS.

- [ ] **Step 7: Verify no old imports remain**

```bash
rg "runtime\\.(errors|quota|graph_factory)" backend/app backend/tests
```

Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add backend/app/agent/runtime backend/tests/agent/runtime/test_runtime_support.py \
  docs/specs/2026-07-12-backend-bloat-diagnosis.md \
  docs/specs/2026-07-14-backend-directory-redesign.md
git commit -m "refactor: 合并 agent runtime 顶层碎片"
```

---

### Task 3: P0-5 Merge `observability/` Package

**Files:**
- Create: `backend/app/observability.py`
- Delete: `backend/app/observability/`
- Modify imports from `app.observability.lifecycle` and `app.observability.metrics`
- Test: `backend/tests/observability/test_observability_module.py`
- Modify docs: both source specs

- [ ] **Step 1: Add module-level tests**

Create `backend/tests/observability/test_observability_module.py`:

```python
"""Observability module tests."""

import pytest

from app.observability import (
    AgentLifecycleEvent,
    increment_counter,
    lifecycle_event_names,
    reset_metrics,
    session_summary_generated_total,
)

pytestmark = pytest.mark.no_db


def test_lifecycle_event_names_are_exported() -> None:
    assert AgentLifecycleEvent.LLM_CALL.value in lifecycle_event_names()


def test_counter_helpers_are_exported() -> None:
    reset_metrics()
    increment_counter("session_summary_generated_total")
    assert session_summary_generated_total() == 1
```

- [ ] **Step 2: Create `backend/app/observability.py`**

Move the contents of `lifecycle.py` and `metrics.py` into one module with this public export list:

```python
__all__ = [
    "AgentLifecycleEvent",
    "get_counter",
    "increment_counter",
    "lifecycle_event_names",
    "reset_metrics",
    "session_summary_failed_total",
    "session_summary_generated_total",
    "session_summary_skipped_total",
]
```

- [ ] **Step 3: Update imports**

Replace:

```python
from app.observability.lifecycle import AgentLifecycleEvent
from app.observability.metrics import increment_counter
```

with:

```python
from app.observability import AgentLifecycleEvent, increment_counter
```

- [ ] **Step 4: Delete package directory**

```bash
git rm backend/app/observability/__init__.py \
  backend/app/observability/lifecycle.py \
  backend/app/observability/metrics.py
```

- [ ] **Step 5: Run task tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/observability/test_observability_module.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/observability.py backend/tests/observability/test_observability_module.py \
  docs/specs/2026-07-12-backend-bloat-diagnosis.md \
  docs/specs/2026-07-14-backend-directory-redesign.md
git commit -m "refactor: 合并 observability 微型包"
```

---

### Task 4: P0-6 Merge Agent Application Three Helper Fragments

**Files:**
- Modify: `backend/app/agent/application/chat_use_case_helpers.py`
- Delete: `backend/app/agent/application/context_invalidation.py`
- Delete: `backend/app/agent/application/context_memory.py`
- Delete: `backend/app/agent/application/response_trace.py`
- Modify imports that reference these three modules
- Test: `backend/tests/agent/application/test_chat_runtime_helpers.py`
- Modify docs: both source specs

- [ ] **Step 1: Add helper export tests**

Create `backend/tests/agent/application/test_chat_runtime_helpers.py`:

```python
"""Chat runtime helper consolidation tests."""

import pytest

from app.agent.application import chat_use_case_helpers as helpers

pytestmark = pytest.mark.no_db


def test_chat_runtime_helpers_exports_context_and_trace_helpers() -> None:
    assert hasattr(helpers, "invalidate_context_cache")
    assert hasattr(helpers, "load_memory_context")
    assert hasattr(helpers, "build_response_trace_metadata")
```

If any of the expected function names differ in current code, use the exact existing names from the three deleted files and update this test before implementation.

- [ ] **Step 2: Move functions into `chat_use_case_helpers.py`**

Copy each public function from:

```text
backend/app/agent/application/context_invalidation.py
backend/app/agent/application/context_memory.py
backend/app/agent/application/response_trace.py
```

into:

```text
backend/app/agent/application/chat_use_case_helpers.py
```

Do not change function behavior.

- [ ] **Step 3: Update imports**

Replace old imports like:

```python
from app.agent.application.context_memory import load_memory_context
```

with:

```python
from app.agent.application.chat_use_case_helpers import load_memory_context
```

- [ ] **Step 4: Delete old files**

```bash
git rm backend/app/agent/application/context_invalidation.py \
  backend/app/agent/application/context_memory.py \
  backend/app/agent/application/response_trace.py
```

- [ ] **Step 5: Run tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider \
  tests/agent/application/test_chat_runtime_helpers.py \
  tests/agent/test_chat_use_case.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agent/application backend/tests/agent/application/test_chat_runtime_helpers.py \
  docs/specs/2026-07-12-backend-bloat-diagnosis.md \
  docs/specs/2026-07-14-backend-directory-redesign.md
git commit -m "refactor: 合并 chat runtime 辅助碎片"
```

---

### Task 5: P1-1 Remove `MemoryServicePort`

**Files:**
- Modify: `backend/app/memory/service.py`
- Delete or empty-remove: `backend/app/memory/ports.py`
- Modify imports from `app.memory.ports`
- Test: `backend/tests/memory/test_memory_service_contract.py`

- [ ] **Step 1: Add concrete service contract test**

Create `backend/tests/memory/test_memory_service_contract.py`:

```python
"""Memory service concrete contract tests."""

import pytest

from app.memory.service import InMemoryMemoryService

pytestmark = pytest.mark.no_db


def test_memory_service_exposes_runtime_methods() -> None:
    service = InMemoryMemoryService()

    assert hasattr(service, "retrieve")
    assert hasattr(service, "observe")
```

- [ ] **Step 2: Replace Protocol imports**

Any function currently annotated with `MemoryServicePort` should use `InMemoryMemoryService` or a local callable shape if a concrete import would create a cycle.

- [ ] **Step 3: Delete `ports.py` if it becomes unused**

```bash
rg "MemoryServicePort|app\\.memory\\.ports" backend/app backend/tests
```

Expected: no output after migration.

Then:

```bash
git rm backend/app/memory/ports.py
```

- [ ] **Step 4: Run tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/memory/test_memory_service_contract.py tests/test_agent_service.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/memory backend/tests/memory/test_memory_service_contract.py \
  docs/specs/2026-07-12-backend-bloat-diagnosis.md
git commit -m "refactor: 删除单实现 MemoryServicePort"
```

---

### Task 6: P1-2 Remove `_ComparableStage(Protocol)`

**Files:**
- Modify: `backend/app/services/crop_service.py`
- Test: existing crop service/API tests

- [ ] **Step 1: Locate the private Protocol**

Run:

```bash
rg "_ComparableStage|Protocol" backend/app/services/crop_service.py
```

- [ ] **Step 2: Replace private Protocol**

If the Protocol only constrains stage comparison fields, replace it with a concrete helper using `Any` and explicit attribute access:

```python
def _stage_order_value(stage: Any) -> int:
    return int(getattr(stage, "order_index", 0) or 0)
```

Do not introduce a new Protocol.

- [ ] **Step 3: Run tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/test_cost.py tests/api/test_planting_operations.py -q
```

Use the closest crop/cycle tests if these files no longer cover crop stage behavior.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/crop_service.py docs/specs/2026-07-12-backend-bloat-diagnosis.md
git commit -m "refactor: 删除 crop service 私有 Protocol"
```

---

### Task 7: P1-3 Evaluate And Remove `core/compat.py`

**Files:**
- Modify: `backend/app/core/compat.py` or delete it
- Modify all imports of `app.core.compat.StrEnum`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Confirm Python baseline**

Run:

```bash
python --version
rg "python_requires|requires-python|python =" pyproject.toml backend/requirements.txt requirements.txt
```

Proceed with deletion only if project baseline is Python 3.11+.

- [ ] **Step 2: Replace imports**

Replace:

```python
from app.core.compat import StrEnum
```

with:

```python
from enum import StrEnum
```

- [ ] **Step 3: Delete compat file**

```bash
rg "app\\.core\\.compat|from app.core.compat" backend/app backend/tests
```

Expected: no output.

Then:

```bash
git rm backend/app/core/compat.py
```

- [ ] **Step 4: Run tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/test_config.py tests/test_mongo_config.py -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests docs/specs/2026-07-12-backend-bloat-diagnosis.md
git commit -m "refactor: 使用标准库 StrEnum"
```

---

### Task 8: D0 Add `app.agent.application` Compatibility Before Migration

**Files:**
- Add compatibility tests under `backend/tests/agent/application/`
- Modify only compatibility surfaces needed for dynamic import and monkeypatch stability

- [ ] **Step 1: Add dynamic import compatibility test**

```python
"""Application migration compatibility tests."""

from importlib import import_module

import pytest

pytestmark = pytest.mark.no_db


def test_old_agent_application_import_path_still_loads_chat_use_case() -> None:
    module = import_module("app.agent.application.chat_use_case")

    assert hasattr(module, "ChatUseCase")
```

- [ ] **Step 2: Run test**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/application -q
```

Expected: PASS before and after future migration. This task may be a no-op if the old package already exists.

- [ ] **Step 3: Commit only if a compatibility change was required**

```bash
git add backend/tests/agent/application
git commit -m "test: 锁定 application 旧路径兼容"
```

---

### Task 9: C0 Add `app.agent.skills` Compatibility Before Migration

**Files:**
- Add compatibility tests under `backend/tests/skills/`
- Modify only compatibility surfaces needed for dynamic import and monkeypatch stability

- [ ] **Step 1: Add dynamic import compatibility test**

```python
"""Skill package migration compatibility tests."""

from importlib import import_module

import pytest

pytestmark = pytest.mark.no_db


def test_old_agent_skills_import_path_still_loads_registry() -> None:
    module = import_module("app.agent.skills.registry")

    assert module is not None
```

- [ ] **Step 2: Run tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/skills/test_skill_registry.py tests/skills/test_skill_metadata.py -q
```

- [ ] **Step 3: Commit only if a compatibility change was required**

```bash
git add backend/tests/skills
git commit -m "test: 锁定 skills 旧路径兼容"
```

---

### Task 10: D1-D2 Move `agent/application` To `app/application`

**Files:**
- Move: `backend/app/agent/application/` to `backend/app/application/`
- Create compatibility package: `backend/app/agent/application/`
- Update imports from `app.agent.application` to `app.application` in production code
- Keep tests using old path until compatibility is proven

- [ ] **Step 1: Move package**

```bash
git mv backend/app/agent/application backend/app/application
mkdir -p backend/app/agent/application
```

- [ ] **Step 2: Add compatibility `__init__.py`**

```python
"""Compatibility package for app.agent.application.

New code must import from app.application. This package remains temporarily for
tests and dynamic monkeypatch paths during directory migration.
"""
```

- [ ] **Step 3: Add per-module re-export files for modules still referenced by tests**

For each old module path still found by:

```bash
rg "app\\.agent\\.application" backend/app backend/tests
```

create a file such as `backend/app/agent/application/chat_use_case.py`:

```python
"""Compatibility re-export for app.application.chat_use_case."""

from app.application.chat_use_case import *  # noqa: F403
```

- [ ] **Step 4: Update production imports**

Production code should use:

```python
from app.application.chat_use_case import ChatUseCase
```

not:

```python
from app.agent.application.chat_use_case import ChatUseCase
```

- [ ] **Step 5: Run tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent tests/api -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests docs/specs/2026-07-14-backend-directory-redesign.md
git commit -m "refactor: 拆出 application 业务编排层"
```

---

### Task 11: C1-C3 Move `agent/skills` To `app/skills`

**Files:**
- Move: `backend/app/agent/skills/` to `backend/app/skills/`
- Create compatibility package: `backend/app/agent/skills/`
- Update production imports from `app.agent.skills` to `app.skills`

- [ ] **Step 1: Move package**

```bash
git mv backend/app/agent/skills backend/app/skills
mkdir -p backend/app/agent/skills
```

- [ ] **Step 2: Add compatibility `__init__.py`**

```python
"""Compatibility package for app.agent.skills.

New code must import from app.skills. This package remains temporarily for
registry, dynamic import, and monkeypatch compatibility during migration.
"""

from app.skills import *  # noqa: F403
```

- [ ] **Step 3: Add compatibility re-exports for registry modules**

For each old registry path found by:

```bash
rg "app\\.agent\\.skills\\.registry" backend/app backend/tests
```

create a matching re-export file under `backend/app/agent/skills/registry/`.

- [ ] **Step 4: Update production imports**

Production code should import:

```python
from app.skills.registry import load_skill_registry
```

not:

```python
from app.agent.skills.registry import load_skill_registry
```

- [ ] **Step 5: Run tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/skills tests/agent/router -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app backend/tests docs/specs/2026-07-14-backend-directory-redesign.md
git commit -m "refactor: 拆出 skills 业务能力层"
```

---

### Task 12: B3 Move Agent Root Business Files

**Files:**
- Move `backend/app/agent/advisor.py` to `backend/app/application/advice/advisor.py`
- Move `backend/app/agent/report.py` to `backend/app/application/report.py`
- Move `backend/app/agent/skill_coverage.py` to `backend/app/platforms/evaluation/skill_coverage.py` after platforms exists, or defer until Task 16
- Move router-related root files into `backend/app/agent/router/`
- Move `backend/app/agent/llm.py` to `backend/app/core/llm.py`
- Move `backend/app/agent/assistant_roles.py` to `backend/app/core/config/roles.py`

- [ ] **Step 1: Split this task into separate PRs before implementation**

This task is intentionally a group from Decision B. Before coding, create one worktree PR per source file group:

```text
B3a advisor/report
B3b intent_router/tool_selector/tool_selection_rules
B3c llm/assistant_roles
B3d skill_coverage after platforms migration
```

- [ ] **Step 2: For each subtask, preserve old imports with compatibility re-export**

Example:

```python
"""Compatibility re-export for moved advisor module."""

from app.application.advice.advisor import *  # noqa: F403
```

- [ ] **Step 3: Run scoped tests per subtask**

Use:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent tests/api -q
```

- [ ] **Step 4: Commit each subtask separately**

Use messages:

```bash
git commit -m "refactor: 迁移 agent advisor 到 application"
git commit -m "refactor: 迁移 agent router 根文件"
git commit -m "refactor: 迁移 agent llm 配置入口"
```

---

### Task 13: E1-E4 Replace LangGraph With Runtime Loop

**Files:**
- Create: `backend/app/agent/runtime/loop.py`
- Modify: graph/advisor/chat entrypoints that call `compile_advisor_graph`
- Remove `langgraph` only after behavior parity

- [ ] **Step 1: Add loop contract tests**

Create tests that assert:

```python
"""Runtime loop contract tests."""

import pytest

from app.agent.runtime.loop import run_agent_loop

pytestmark = pytest.mark.no_db


def test_run_agent_loop_is_callable() -> None:
    assert callable(run_agent_loop)
```

- [ ] **Step 2: Implement pure Python loop**

```python
async def run_agent_loop(state: AgentState, max_steps: int = 15) -> AgentState:
    for _ in range(max_steps):
        state = await _llm_node(state)
        if _should_continue(state) != "tools":
            return state
        state = await _parallel_tool_node(state)
    return state
```

- [ ] **Step 3: Replace call sites one at a time**

Do not delete `compile_advisor_graph` until old and new paths both pass tests.

- [ ] **Step 4: Remove LangGraph dependency**

Only after no code imports `langgraph`:

```bash
rg "langgraph" backend/app backend/tests backend/requirements.txt
```

Then remove `langgraph` from requirements. Do not remove `langchain-core`.

---

### Task 14: P2-1 / A1-A3 Extract Platform Shared Prerequisites

**Files:**
- Create: `backend/app/platforms/shared/`
- Move shared judge/repository selector code only after import graph is understood

- [ ] **Step 1: Map current dependencies**

```bash
rg "judge_service|build_data_flywheel_repository|rule_engine" backend/app backend/tests -n
```

- [ ] **Step 2: Move `judge_service` to shared**

Use compatibility re-export at old path for one PR.

- [ ] **Step 3: Move `repository_selector` to shared**

Ensure `backend/app/infra/repository_runtime.py` no longer imports `app.modules.data_flywheel`.

- [ ] **Step 4: Decide `rule_engine`**

If both evaluation and data flywheel import it, move to shared; otherwise leave it with evaluation.

---

### Task 15: P2-3 / P2-4 Reduce Document Repository Backends

**Precondition:** Do not implement until production config, settings defaults, tests, rollback strategy, and Mongo migration status are confirmed.

- [ ] **Step 1: Produce confirmation note**

Create a short doc section in the PR body with:

```text
production storage backend:
settings default storage backend:
tests that require mysql/dual/mongo-read:
rollback strategy:
Mongo migration OpenSpec status:
```

- [ ] **Step 2: Only then remove unused backends**

Keep Mongo repositories. Remove MySQL, DualWrite, and MongoRead only when the confirmation note is complete.

---

### Task 16: A4-A6 Move Evaluation And Data Flywheel Into `platforms/`

**Precondition:** Task 14 and Task 15 must be complete.

- [ ] **Step 1: Move evaluation**

```bash
git mv backend/app/evaluation backend/app/platforms/evaluation
```

- [ ] **Step 2: Move data flywheel**

```bash
git mv backend/app/modules/data_flywheel backend/app/platforms/data_flywheel
```

- [ ] **Step 3: Update imports**

Use `rg "app\\.(evaluation|modules\\.data_flywheel)" backend/app backend/tests`.

- [ ] **Step 4: Update architecture docs**

Update:

```text
docs/architecture/boundaries.md
docs/architecture/overview.md
```

---

### Task 17: P2-6 Repository Hygiene

**Files:**
- Remove empty directories if tracked content does not exist.
- Move root tests under mirrored directories.

- [ ] **Step 1: Empty directory scan**

```bash
find backend/app -type d -empty
```

- [ ] **Step 2: Root test scan**

```bash
find backend/tests -maxdepth 1 -type f -name 'test_*.py' | sort
```

- [ ] **Step 3: Move tests by source mirror in small PR batches**

Examples:

```bash
git mv backend/tests/test_config.py backend/tests/core/test_config.py
git mv backend/tests/test_cost.py backend/tests/services/test_cost.py
```

Run moved tests after every batch.

---

### Task 18: P3 Governance Sensors

**Files:**
- `.claude/rules/python-style.md`
- `scripts/check-*.sh`
- matching docs under `docs/architecture/` or `docs/conventions/`

- [ ] **Step 1: Add Protocol sensor**

The sensor must fail newly added Protocol/ABC without documented two implementations.

- [ ] **Step 2: Add backend implementation proof sensor**

The sensor must fail newly added backend implementation classes without a referenced production config or migration note.

- [ ] **Step 3: Add Guide+Sensor pairing entry**

Run:

```bash
bash scripts/check-guide-sensor-pairing.sh
```

---

## Self-Review

Spec coverage:

- Diagnosis P0/P1/P2/P3 rows are represented in Tasks 1-18.
- Directory redesign decisions A/B/C/D/E are represented in Tasks 10-16.
- P0-1 and P0-2 are recorded as completed baseline and excluded from dispatch.

Known constraints:

- `document_repository_*` deletion is intentionally blocked until confirmation evidence exists.
- `LangGraph` removal must not remove `langchain-core`.
- `application/` and `skills/` migrations must keep temporary compatibility layers until production code and tests are fully migrated.

Placeholder scan:

- No disallowed placeholder patterns are present in task instructions.
- Risky tasks name explicit preconditions and stop conditions.
