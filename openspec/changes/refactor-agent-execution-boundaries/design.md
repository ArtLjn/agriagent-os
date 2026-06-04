## Context

The backend Agent platform already has target boundaries for application, runtime, executor, prompt, context, memory, evaluation, and observability. The current implementation still routes chat through `services.agent_service`, keeps fallback orchestration in `agent.advisor`, and lets runtime nodes construct prompt/context and execute tool policy details.

Accounting shows the problem clearly: the first request creates a pending action, and the confirmation request later executes it. Today the pending confirmation path exists in both `services.agent_service` and `agent.advisor`, with different execution mechanisms and cache invalidation behavior. This change turns that flow into one owned executor path.

The deployment constraint is a small 2h4g server. Long-term memory and RAG should remain external-future concerns; this change must not add vector database, embedding workers, or in-process RAG pipelines.

## Goals / Non-Goals

**Goals:**

- Make pending action confirmation behavior single-source and shared by non-streaming, streaming, and advisor fallback paths.
- Move chat lifecycle orchestration toward `agent/application`, including conversation persistence, pending action response assembly, memory observation, and trace-related post-processing.
- Make `agent/executor` the owner of write-tool confirmation execution and cache invalidation.
- Reduce runtime coupling to prompt/context/memory construction through prepared inputs or narrow ports.
- Add architecture checks that prevent the same duplicate paths from returning.
- Preserve existing `/agent/chat` and `/agent/chat/stream` API behavior.

**Non-Goals:**

- Do not implement long-term memory storage, embeddings, vector search, or a RAG service.
- Do not redesign all skills or migrate business services into new modules.
- Do not change external API request/response schemas unless existing tests reveal an undocumented inconsistency.
- Do not remove all compatibility imports in one step; compatibility wrappers can remain if they delegate to the new owner.

## Decisions

### Centralize pending action execution in Agent Executor

Create a single pending action executor service under `agent/executor`, responsible for:

- detecting confirm/cancel/modify intent for an existing pending action,
- executing confirmed write skills,
- handling chained follow-up actions such as create-template-then-create-cycle,
- invalidating skill cache groups,
- recording skill trace events consistently,
- returning a structured result to application/advisor callers.

Alternative considered: keep the current service/advisor split and add tests. This keeps implementation cheaper in the short term but preserves duplicate behavior and forces every future write-skill change to update two paths.

### Promote Agent Application as the lifecycle owner

`agent/application/chat_use_case.py` becomes the primary owner for chat lifecycle steps: resolve session, save user message, call pending executor when present, invoke advisor/runtime only when no immediate pending decision exists, save assistant response, submit memory observation, and assemble pending action response metadata.

`services.agent_service` remains as a compatibility wrapper during migration but must not retain independent pending execution logic.

Alternative considered: move everything directly into `advisor.py`. This would make the code path shorter but would keep HTTP-adjacent persistence, memory observation, and runtime fallback concerns inside the advisor compatibility entry.

### Thin Runtime through prepared request state

Runtime should continue to own LangGraph node execution and LLM/tool-call loop mechanics, but it should gradually consume prepared state for system prompt, context bundle, memory context, selected tools, and quota result. The first implementation can introduce ports and helper objects before deleting every compatibility path.

Alternative considered: rewrite runtime nodes fully in one step. That increases regression risk for tool calling, streaming, and quota behavior.

### Keep memory lightweight until external RAG exists

Long-term memory and retrieval remain interface-only. The current process can keep short-term/session behavior and observation events, but any durable vector/knowledge memory should be provided later by a separate RAG/memory service through the Memory Service port.

Alternative considered: embed a vector store into the backend now. This conflicts with resource limits and would mix business API traffic with memory indexing workloads.

### Add sensors for ownership rules

Extend architecture checks to catch:

- new `agent/application` imports of legacy `services.agent_service` orchestration,
- direct pending action execution outside the executor service,
- runtime imports through prompt/context compatibility entry points that bypass prepared inputs,
- write skills that are not covered by confirmation policy.

Alternative considered: rely on code review. This project already uses Guide+Sensor pairing, so architecture intent should be executable.

## Risks / Trade-offs

- Pending behavior regression -> cover create-cost-record confirmation, cancel, modify, stream, and chained actions with focused tests before moving callers.
- Streaming/non-streaming drift -> both paths must call the same pending executor and share fixture expectations.
- Compatibility wrappers hide old behavior -> add checks that wrappers delegate and do not duplicate execution logic.
- Runtime thinning may take multiple patches -> split work into small steps with behavior-preserving tests rather than a single large rewrite.
- No long-term memory now means less personalization -> keep Memory Service contracts stable so a future external RAG service can plug in without changing Agent callers.

## Migration Plan

1. Add focused tests that describe current accounting pending flow for non-streaming and streaming chat.
2. Introduce the executor-owned pending action service and move shared confirmation/cancel/chaining/cache invalidation behavior into it.
3. Update `services.agent_service` and `agent.advisor` to delegate pending decisions to the new service.
4. Move chat lifecycle orchestration from `services.agent_service` into `agent/application`, leaving service functions as compatibility wrappers.
5. Introduce prepared runtime input structures or ports for prompt/context/memory and update runtime call sites incrementally.
6. Extend architecture checks and runtime tests to enforce the new ownership boundaries.

Rollback strategy: keep compatibility wrappers during migration. If runtime refactoring regresses, revert the specific runtime-preparation step while retaining the centralized pending executor if its tests pass.

## Open Questions

- Should pending actions remain keyed only by `farm_id`, or should this change introduce a `session_id`-aware key to avoid multi-tab collisions?
- Should confirmed write-skill execution return a structured object with `reply`, `skills_called`, `cache_groups_cleared`, and `follow_up_pending`, or is reply plus metadata enough for the current UI?
- Should quota checks remain in runtime initially, or move to application before runtime thinning starts?
