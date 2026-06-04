## Why

The current Agent request path has clear target architecture, but write execution, pending action confirmation, application orchestration, and runtime responsibilities are still split across legacy service and advisor paths. This creates duplicated behavior for accounting and other write skills, makes confirmation/caching/trace semantics harder to keep consistent, and prevents the Agent application boundary from becoming the stable entry point.

## What Changes

- Move pending action handling into one Agent executor service used by non-streaming chat, streaming chat, and advisor fallback paths.
- Make `agent/application` the primary orchestration boundary for chat request lifecycle, while keeping legacy `services.agent_service` as a temporary compatibility wrapper.
- Thin Agent Runtime so it consumes prepared request context and delegates write confirmation/tool execution instead of owning platform orchestration.
- Keep long-term memory and retrieval as lightweight interfaces with empty or short-term-only behavior for now; do not introduce an in-process RAG/vector stack in this change.
- Strengthen architecture sensors so future code cannot silently reintroduce duplicate pending action execution or route new chat orchestration through legacy services.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `llm-tool-calling`: Clarify that Tool Executor owns pending action confirmation execution, write-skill cache invalidation, and unified tool-call trace semantics.
- `agent-platform-architecture`: Clarify that Agent Application owns the chat lifecycle orchestration and Runtime consumes prepared prompt/context/tool inputs.
- `agent-memory-foundation`: Clarify that long-term memory and retrieval remain interface-only until an external RAG/memory service is introduced.

## Impact

- Affected backend code: `backend/app/agent/application/`, `backend/app/agent/executor/`, `backend/app/agent/runtime/`, `backend/app/agent/advisor.py`, `backend/app/services/agent_service.py`, `backend/app/infra/pending_actions.py`, and Agent tests.
- Affected validation: `scripts/check-layer-deps.sh` and related architecture tests should gain checks for the new ownership boundaries.
- External API behavior should remain compatible for `/agent/chat` and `/agent/chat/stream`.
- No new external infrastructure, vector database, embedding model, or RAG service is introduced by this change.
