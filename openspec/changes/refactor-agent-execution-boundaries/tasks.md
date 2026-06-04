## 1. Baseline Coverage

- [ ] 1.1 Add focused tests for non-streaming `create_cost_record` pending creation, confirmation, cancellation, and modify behavior.
- [ ] 1.2 Add focused tests for streaming `create_cost_record` pending creation and confirmation behavior.
- [ ] 1.3 Add tests for chained pending action behavior that creates a crop template before resuming crop cycle creation.
- [ ] 1.4 Add tests that verify confirmed write skills clear the expected cache groups and record skill trace events.

## 2. Pending Action Executor

- [ ] 2.1 Create an Agent Executor pending action service with structured results for handled, unhandled, confirmed, canceled, failed, and follow-up states.
- [ ] 2.2 Move confirm/cancel/modify intent handling into the new executor service.
- [ ] 2.3 Move write-skill execution, chained follow-up creation, cache invalidation, and trace recording into the new executor service.
- [ ] 2.4 Update `agent.advisor` to delegate pending action handling to the executor service.
- [ ] 2.5 Update `services.agent_service` to delegate pending action handling to the executor service without retaining duplicate execution logic.

## 3. Application Lifecycle Ownership

- [ ] 3.1 Move non-streaming chat lifecycle orchestration into `agent/application/chat_use_case.py`.
- [ ] 3.2 Move streaming chat lifecycle orchestration into Agent Application while preserving existing SSE response behavior.
- [ ] 3.3 Convert `services.agent_service` chat functions into compatibility wrappers that delegate to Agent Application.
- [ ] 3.4 Ensure conversation persistence, AgentRecord persistence, pending action response assembly, and Memory observation are owned by Agent Application.

## 4. Runtime Boundary Thinning

- [ ] 4.1 Introduce prepared runtime input structures or ports for prompt, context, memory, selected tools, and quota decisions.
- [ ] 4.2 Update runtime LLM node call sites to consume prepared inputs where available while preserving compatibility fallback.
- [ ] 4.3 Move pending action confirmation execution out of runtime/tool compatibility paths and keep runtime tool node limited to interception/delegation.
- [ ] 4.4 Add regression tests for LLM tool selection, direct read-tool routing, prompt/context trace, and quota behavior.

## 5. Memory Scope Guardrails

- [ ] 5.1 Keep long-term memory and retrieval implementations lightweight and returning empty results when no external service is configured.
- [ ] 5.2 Add tests proving Agent chat continues without configured RAG, vector database, embedding model, or retrieval backend.
- [ ] 5.3 Document the future external RAG/memory service integration point through the existing Memory Service port.

## 6. Architecture Sensors

- [ ] 6.1 Extend architecture checks to fail when new pending action execution logic is added outside Agent Executor.
- [ ] 6.2 Extend architecture checks to flag new Agent Application orchestration imports from `services.agent_service`.
- [ ] 6.3 Extend architecture checks to flag Runtime imports that bypass prepared prompt/context/memory inputs through compatibility entry points.
- [ ] 6.4 Run `ruff check .`, `ruff format .`, `bash scripts/check-layer-deps.sh`, and focused backend tests for the touched modules.
