# Context Engine Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the first production slice of the Context Engine redesign: a block registry, better compression metadata, structured tool-result compaction, and admin-web LLM Context observability that reflects the final compressed prompt.

**Architecture:** Keep `ContextBuilder` and existing selector imports compatible, but add a central `registry.py` and use it from allowlist/render/trace paths. Upgrade final prompt budget tracing to `final_llm_context` schema v2 so admin-web can show the exact post-compression system prompt, messages, context blocks, budget, and compression events.

**Tech Stack:** FastAPI backend with Python dataclasses, LangChain message types, pytest; React + TypeScript + Ant Design admin-web with Vitest.

---

## File Structure

- Create `backend/app/context/registry.py`: central block registry and category metadata.
- Create `backend/app/context/compression.py`: compression decision/event dataclasses and tool-result compressor.
- Modify `backend/app/context/allowlist.py`: derive prompt allowlist from registry while keeping forbidden keys.
- Modify `backend/app/context/renderer.py`: derive section mapping from registry.
- Modify `backend/app/context/trace.py`: expose reusable safe text helpers or build runtime context snapshot payload.
- Modify `backend/app/agent/runtime/messages.py`: compact old tool results with structured summaries.
- Modify `backend/app/agent/runtime/final_prompt_budget.py`: report richer before/after budget and use structured tool-result compression.
- Modify `backend/app/agent/runtime/node_helpers.py`: emit `final_llm_context` schema v2.
- Create/modify backend tests under `backend/tests/context/` and `backend/tests/test_final_prompt_budget.py`, `backend/tests/test_sliding_window.py`.
- Modify `admin-web/src/pages/Playground/traceMetrics.ts`: parse snapshot v2.
- Modify `admin-web/src/pages/Playground/LlmContextVisualView.tsx`: show block decisions, compression, messages timeline.
- Modify/add admin-web Playground tests for the new snapshot shape.
- Add `docs/specs/2026-07-26-agent-context-engine-and-observability-design.md` to the feature branch.

---

### Task 1: Backend Context Registry

**Files:**
- Create: `backend/app/context/registry.py`
- Modify: `backend/app/context/allowlist.py`
- Modify: `backend/app/context/renderer.py`
- Test: `backend/tests/context/test_registry.py`

- [ ] **Step 1: Write registry tests**

Create `backend/tests/context/test_registry.py` with assertions:

```python
from app.context.allowlist import is_allowed_key
from app.context.registry import (
    BLOCK_REGISTRY,
    ContextCategory,
    block_spec,
    prompt_allowed_keys,
    section_for_key,
)
from app.context.renderer import ContextRenderer


def test_existing_context_keys_are_registered() -> None:
    expected = {
        "farm",
        "cycle",
        "ledger",
        "weather",
        "user_settings",
        "active_task_state",
        "pending_action",
        "temporary_task_state",
        "rag_knowledge",
        "retrieval",
        "tool_result_summary",
        "short_term_recent",
        "short_term_summary",
        "conversation",
        "conversation_summary",
        "long_term_memory",
        "output_contract",
        "citation_rule",
        "clarification_rule",
    }

    assert expected.issubset(BLOCK_REGISTRY)


def test_registry_drives_allowlist_and_renderer_sections() -> None:
    assert "conversation_summary" in prompt_allowed_keys()
    assert is_allowed_key("conversation_summary") is True
    assert block_spec("rag_knowledge").category == ContextCategory.EVIDENCE
    assert section_for_key("rag_knowledge") == "Evidence"
    assert ContextRenderer().section_name_for_key("active_task_state") == "Task"


def test_unknown_keys_are_not_prompt_allowed_but_fallback_to_context_section() -> None:
    assert is_allowed_key("unregistered_debug_blob") is False
    assert section_for_key("unregistered_debug_blob") == "Context"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pytest backend/tests/context/test_registry.py -v
```

Expected: fails because `app.context.registry` does not exist.

- [ ] **Step 3: Implement registry**

Create `backend/app/context/registry.py` with `ContextCategory`, `ContextBlockSpec`, `BLOCK_REGISTRY`, `block_spec()`, `prompt_allowed_keys()`, and `section_for_key()`. Include all block keys listed in the test. Unknown keys return `None` from `block_spec()` and `"Context"` from `section_for_key()`.

- [ ] **Step 4: Wire allowlist and renderer**

Update `allowlist.py` so `ALLOWED_CONTEXT_KEYS = prompt_allowed_keys() | legacy keys that are still intentionally accepted`. Keep `FORBIDDEN_CONTEXT_KEYS` as explicit denial list and ensure forbidden wins.

Update `renderer.py` so `section_name_for_key()` calls `section_for_key(key)`.

- [ ] **Step 5: Run registry tests**

Run:

```bash
pytest backend/tests/context/test_registry.py backend/tests/context/test_renderer.py backend/tests/context/test_allowlist.py -v
```

Expected: all pass.

---

### Task 2: Backend Compression and Final Snapshot V2

**Files:**
- Create: `backend/app/context/compression.py`
- Modify: `backend/app/agent/runtime/messages.py`
- Modify: `backend/app/agent/runtime/final_prompt_budget.py`
- Modify: `backend/app/agent/runtime/node_helpers.py`
- Test: `backend/tests/test_final_prompt_budget.py`
- Test: `backend/tests/test_sliding_window.py`
- Test: `backend/tests/context/test_llm_context_snapshot.py`

- [ ] **Step 1: Write compression tests**

Update `backend/tests/test_sliding_window.py` so old `ToolMessage` content is expected to contain:

```text
[工具结果已压缩]
tool: tool_0
```

and recent tool results remain unchanged.

Update `backend/tests/test_final_prompt_budget.py` to assert:

```python
assert "compact_tool_results" in result.actions
assert result.message_count_before == len(messages)
assert result.tool_result_tokens_before >= result.tool_result_tokens_after
assert "tool: get_farm_status" in compacted[1].content
assert "ref: tool_call_id=tc1" in compacted[1].content
```

Create `backend/tests/context/test_llm_context_snapshot.py` with a unit test that calls `_record_final_llm_context_trace()` using a fake collector and a `ContextBundle` containing `farm` and compressed `conversation_summary`. Assert output includes `schema_version == 2`, `runtime_context.sections`, `budget.actions`, and no raw `password=secret`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest backend/tests/test_sliding_window.py backend/tests/test_final_prompt_budget.py backend/tests/context/test_llm_context_snapshot.py -v
```

Expected: fails because structured compression and snapshot v2 are not implemented.

- [ ] **Step 3: Add compression dataclasses and compressor**

Create `backend/app/context/compression.py`:

```python
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CompressionEvent:
    target: str
    key: str
    action: str
    reason: str
    original_tokens: int
    final_tokens: int
    compressor: str
    metadata: dict[str, Any] = field(default_factory=dict)


def compact_tool_result(
    *,
    content: str,
    tool_name: str | None,
    tool_call_id: str,
    status: str | None = None,
    max_summary_chars: int = 220,
) -> str:
    clean = " ".join(str(content or "").split())
    summary = clean[:max_summary_chars].rstrip()
    if len(clean) > max_summary_chars:
        summary += "..."
    return "\n".join(
        [
            "[工具结果已压缩]",
            f"tool: {tool_name or 'unknown'}",
            f"status: {status or 'unknown'}",
            f"summary: {summary or '工具已执行，旧结果已从上下文压缩。'}",
            f"ref: tool_call_id={tool_call_id}",
        ]
    )
```

- [ ] **Step 4: Wire structured tool result compaction**

In `messages.py`, build a `tool_call_id -> tool_name` map by scanning previous `AIMessage.tool_calls`, and replace old long `ToolMessage` content with `compact_tool_result(...)` instead of `[已执行 unknown]`.

In `final_prompt_budget.py`, add fields to `FinalPromptBudgetResult`: `message_count_before`, `message_count_after`, `tool_result_tokens_before`, `tool_result_tokens_after`, `compression_events`. Use `compact_tool_result()` for oversized `ToolMessage`.

- [ ] **Step 5: Emit final_llm_context v2**

In `node_helpers.py`, update `_record_final_llm_context_trace()` output to include:

- `schema_version: 2`
- `runtime_context.sections`: rendered section/block metadata with safe previews
- `messages`: final messages after budget compaction
- `budget`: `final_budget.summary()`
- `compression`: counts from context bundle and final budget events

Do not remove existing fields `system_prompt`, `messages`, `context_blocks`, or `budget`.

- [ ] **Step 6: Run backend compression tests**

Run:

```bash
pytest backend/tests/test_sliding_window.py backend/tests/test_final_prompt_budget.py backend/tests/context/test_llm_context_snapshot.py -v
```

Expected: all pass.

---

### Task 3: Admin-Web LLM Context Inspector V2

**Files:**
- Modify: `admin-web/src/pages/Playground/traceMetrics.ts`
- Modify: `admin-web/src/pages/Playground/LlmContextVisualView.tsx`
- Test: `admin-web/src/pages/Playground/LlmContextInspector.test.tsx`
- Test: `admin-web/src/pages/Playground/traceMetrics.test.ts`

- [ ] **Step 1: Write frontend parsing tests**

Add a v2 final_llm_context node fixture to `traceMetrics.test.ts`. Assert `extractLatestLlmContextSnapshot()` returns:

- `schemaVersion === 2`
- `runtimeSections[0].name === "Task"`
- `contextBlockDetails[0].key === "active_task_state"`
- `contextBlockDetails[0].decision === "selected"`
- `compression.tool_result_compressed_count === 1`

- [ ] **Step 2: Run frontend tests to verify they fail**

Run:

```bash
pnpm test -- --run admin-web/src/pages/Playground/traceMetrics.test.ts admin-web/src/pages/Playground/LlmContextInspector.test.tsx
```

Expected: fails because v2 fields are not parsed or rendered.

- [ ] **Step 3: Extend snapshot types and parser**

In `traceMetrics.ts`, add:

```ts
export interface PlaygroundLlmContextBlockDetail {
  key: string;
  category: string;
  source: string;
  decision: string;
  compressed: boolean;
  dropped: boolean;
  priority: number | null;
  required: boolean;
  token_estimate: number | null;
  content_preview: string;
}

export interface PlaygroundLlmContextRuntimeSection {
  name: string;
  token_estimate: number | null;
  blocks: PlaygroundLlmContextBlockDetail[];
}
```

Add optional fields to `PlaygroundLlmContextSnapshot`: `schemaVersion`, `runtimeSections`, `contextBlockDetails`, `compression`.

Parse `output.runtime_context.sections` when present; otherwise keep the current system prompt parsing fallback.

- [ ] **Step 4: Render block decisions**

In `LlmContextVisualView.tsx`, update Context Blocks panel:

- group blocks by `category`
- display `selected/compressed/dropped/required`
- show token estimate and reason when present
- keep old `snapshot.contextBlocks` fallback

Update Runtime Context panel to prefer `snapshot.runtimeSections` over parsing `systemPrompt`.

- [ ] **Step 5: Run frontend tests**

Run:

```bash
pnpm test -- --run admin-web/src/pages/Playground/traceMetrics.test.ts admin-web/src/pages/Playground/LlmContextInspector.test.tsx
```

Expected: all pass.

---

### Task 4: Integration Tests and Docs Link

**Files:**
- Modify: `docs/farm-manager-design-spec/01_正式设计/03_Context工程.md`
- Test: backend and frontend targeted suites

- [ ] **Step 1: Link the design spec**

Add one paragraph near `03_Context工程.md` section 13:

```markdown
- [Context Engine 重构与 LLM Context 可观测设计](../../specs/2026-07-26-agent-context-engine-and-observability-design.md)：规划 ContextEngine 主入口、六类 Context 注册表、压缩机制优化和 admin-web LLM Context 可观测。
```

- [ ] **Step 2: Run targeted backend tests**

Run:

```bash
pytest backend/tests/context/test_registry.py backend/tests/context/test_renderer.py backend/tests/context/test_allowlist.py backend/tests/test_sliding_window.py backend/tests/test_final_prompt_budget.py backend/tests/context/test_llm_context_snapshot.py -v
```

Expected: all pass.

- [ ] **Step 3: Run targeted frontend tests**

Run:

```bash
pnpm test -- --run admin-web/src/pages/Playground/traceMetrics.test.ts admin-web/src/pages/Playground/LlmContextInspector.test.tsx
```

Expected: all pass.

- [ ] **Step 4: Run lint/format checks**

Run:

```bash
ruff check backend/app/context backend/app/agent/runtime backend/tests/context backend/tests/test_sliding_window.py backend/tests/test_final_prompt_budget.py
pnpm lint
bash scripts/check-complexity-budget.sh
```

Expected: no new failures. If existing unrelated lint failures appear, record them in final notes with exact command output.

- [ ] **Step 5: Commit**

Commit all branch changes with:

```bash
git add backend/app/context backend/app/agent/runtime backend/tests admin-web/src/pages/Playground docs/specs docs/farm-manager-design-spec/01_正式设计/03_Context工程.md docs/superpowers/plans/2026-07-26-context-engine-observability-plan.md
git commit -m "feat: improve context engine observability"
```
