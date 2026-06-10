# Skill Router Optimization Design

## Goal

Build a production-grade Skill Router for farm-manager so LLM tool selection is fast, accurate, and token efficient as the Skill set grows.

The current runtime has a partial progressive disclosure mechanism: `select_tools()` normally narrows tools before `bind_tools()`, but when no rule matches it falls back to all enabled tools. Recent traces show `fallback_all` returning 33 tools for simple planting queries, causing repeated large tool-schema prompts, higher latency, and weaker selection reliability.

This design replaces `fallback_all` with a dedicated router layer that selects domains, intents, risk levels, context dependencies, and a bounded set of concrete tools before the main LLM runs.

## Current Problems

### Full-tool fallback breaks progressive disclosure

`tool_selector.select_tools()` is intended to return a small candidate set, but when rule matching fails it returns all enabled tools. In `session5`, the query "我家有哪些作物栽种" selected 33 tools even though only `get_farm_status` was needed.

### Tool schema tokens are repeatedly paid

Tool definitions are injected into the model request and count toward input tokens. OpenAI recommends keeping the initial tool set small and using tool search or delayed loading when tool surfaces grow. The current 33-tool fallback exceeds that guidance and repeats in the final answer round after tool results.

References:

- OpenAI Function Calling: https://developers.openai.com/api/docs/guides/function-calling
- LangChain Tools and dynamic selection: https://docs.langchain.com/oss/python/langchain/tools
- LangGraph dynamic tool calling: https://changelog.langchain.com/announcements/dynamic-tool-calling-in-langgraph-agents

### Read and write tools share the same fallback pool

Read queries can expose write-confirm tools such as create, manage, delete, and settle skills. Pending confirmation still prevents direct writes, but exposing risky tools increases mis-selection, hallucinated writes, and confirmation confusion.

### Context preloading follows the wrong candidate set

Context policy and preload depend on `selected_tools`. When selection falls back to 33 tools, context dependencies and cache warmup are driven by a polluted candidate set instead of the minimum data needed for the user's intent.

### Multi-intent messages lose actions

The current pending action storage holds one action per farm/session. User messages that contain multiple actions, such as creating a worker and assigning the worker to harvest, can retain only one pending action and drop the follow-up work order.

## Design Principles

- Never expose all tools to the main LLM as a fallback.
- Keep normal tool disclosure to 1-3 tools and complex disclosure to at most 5 tools.
- Separate read and write tools by intent and risk.
- Prefer deterministic routing for common farm workflows.
- Use light routing or retrieval before main LLM tool binding.
- Use persistent, inspectable plans for multi-intent write operations.
- Trace every router decision with candidates, rejected tools, fallback reason, and token estimates.
- If uncertain about a write operation, ask a clarification question instead of exposing high-risk tools.

## Architecture

Add a new router package:

```text
backend/app/agent/router/
  catalog.py        # Builds structured Skill Catalog from metadata and skill docs
  classifier.py     # Classifies domain, intent, risk, entities, and multi-intent frames
  retriever.py      # Retrieves concrete Skill candidates from the Catalog
  policy.py         # Applies permission, risk, pending, fallback, and token budgets
  models.py         # RouterDecision, IntentFrame, ToolCandidate, DisclosureBudget
```

The runtime flow becomes:

```text
User message
  -> SkillRouter.route()
  -> RouterDecision(frames, selected_tools, context_dependencies)
  -> ContextPolicy builds minimum context from RouterDecision
  -> Main LLM binds selected_tools only
  -> ToolExecutor executes read tools or stores write-confirm actions
  -> Final answer LLM summarizes tool results without rebinding all tools
```

## Skill Catalog

The Skill Catalog is the source of truth for tool routing. It normalizes every Skill into structured metadata:

```json
{
  "name": "create_operation_work_order",
  "domain": "operation",
  "intents": ["create_work_order"],
  "risk": "write_confirm",
  "entities": ["worker", "planting_unit", "crop_cycle", "labor"],
  "trigger_examples": ["今天李树去6号棚收水稻"],
  "anti_examples": ["我的作业单有哪些"],
  "context_dependencies": ["workers", "planting_units", "active_cycles"],
  "candidate_group": "operation_write"
}
```

Catalog data should be derived from existing Skill metadata where possible. Missing fields can be added through a small registry file instead of scattering routing hints across runtime code.

## Router Decision

The router returns structured decisions, not raw tool lists:

```json
{
  "frames": [
    {
      "domain": "planting",
      "intent": "query_active_crops",
      "risk": "read",
      "entities": ["crop_cycle"],
      "candidate_tools": ["get_farm_status", "get_crop_cycle_info"],
      "confidence": 0.86
    }
  ],
  "selected_tools": ["get_farm_status"],
  "context_dependencies": ["crop_cycles"],
  "fallback": "safe_read_default",
  "reason": "query_active_crops matched planting status read intent"
}
```

### Candidate Limits

- Normal read query: 1-2 tools.
- Complex read query: up to 5 tools.
- Write intent: one write-confirm tool, plus optional read context tools only if needed.
- Unknown chat or explanation: no tools.
- Unknown farm-status query: safe read default, usually `get_farm_status`.
- Unknown write intent: clarification, no write tool binding.

## Tool Disclosure Budget

Add a hard disclosure budget:

```text
max_tools_default = 3
max_tools_complex = 5
max_write_tools = 1
max_schema_tokens = 1800
```

The router estimates schema cost for candidate tools before `bind_tools()`. If the selected set exceeds budget, the policy layer trims by rank or asks a clarification. It must never fall back to all tools.

## Final Answer Behavior

After tools have returned results, the final answer round should not rebind the original candidate tools by default.

Rules:

- If the previous step produced normal tool results, summarize with no bound tools.
- If the previous step produced a pending action confirmation, return the pending confirmation directly.
- If the router detects that a second read is needed, expose only the newly required read tools.
- Never use `fallback_all` in a final answer round.

This prevents traces like `selected_tools=33 | tool_calls=0` after a tool result.

## Context and Preload

ContextPolicy and preload should consume `RouterDecision.context_dependencies`, not an unbounded selected tool list.

Example:

```json
{
  "selected_tools": ["get_farm_status"],
  "context_dependencies": ["farm", "crop_cycles", "recent_operations"]
}
```

Only the matching selectors run. Cache warmup only runs for dependency-backed data types. Preload logs should show the small dependency set rather than every selected tool name.

## Multi-Intent and Pending Queue

Replace single pending action semantics with an action plan queue.

Example input:

```text
我招了一个工人王大妈工资100一天，早上来了让他去5号棚收水稻了
```

Router plan:

```json
{
  "frames": [
    {
      "intent": "create_worker",
      "tool": "manage_workers",
      "params_hint": {
        "name": "王大妈",
        "default_unit_price": 100,
        "default_pay_type": "daily"
      },
      "requires_confirmation": true
    },
    {
      "intent": "create_work_order",
      "tool": "create_operation_work_order",
      "params_hint": {
        "workers": "王大妈",
        "unit_names": "5号棚",
        "operation_type": "采收",
        "unit_price": 100
      },
      "depends_on": ["create_worker"],
      "requires_confirmation": true
    }
  ]
}
```

Pending storage should evolve from:

```text
(farm_id, session_id) -> PendingAction
```

to:

```text
agent_pending_plans
agent_pending_plan_steps
```

The plan stores `plan_id`, `farm_id`, `session_id`, `status`, `current_step_index`, `raw_user_input`, `router_decision`, and `expires_at`. Each step stores tool name, params, dependencies, confirmation state, execution status, and result/error payload.

### Confirmation Mode

Default to batch confirmation for low and medium risk multi-step plans:

```text
请确认将执行 2 步：

1. 创建工人：王大妈，日薪100元
2. 创建采收作业单：今天，5号棚，工人王大妈，应付100元，未付100元

确认后会创建工人档案、作业单和未付人工。
确认吗？
```

Use step-by-step confirmation when:

- A destructive or high-risk tool is involved.
- Any required target or amount is uncertain.
- A dependency step fails.
- The user corrects one step of the plan.

### Labor Wage Rule

Work order labor entries must not silently default to zero payable amount.

Priority:

1. Use wage stated in the current utterance.
2. Use worker default wage if the worker exists.
3. If neither exists, ask a clarification.
4. Only allow zero wage when the user explicitly says no wage is needed.

## Policy Guard

Policy Guard applies after retrieval and before tool binding:

- Reject disabled tools.
- Reject write tools for read-only intents.
- Enforce admin-only permissions.
- Limit candidate count and schema token budget.
- Prefer direct routes for deterministic read queries.
- Convert ambiguous write intents into clarification prompts.
- Block final-answer rounds from full tool rebinding.
- Preserve pending-plan state before new write planning.

## Trace and Admin Diagnostics

Add a router trace node for every agent turn:

```json
{
  "node_type": "skill_router",
  "input": "我家有哪些作物栽种",
  "frames": [
    {
      "domain": "planting",
      "intent": "query_active_crops",
      "risk": "read"
    }
  ],
  "selected_tools": ["get_farm_status"],
  "rejected_tools": ["create_crop_cycle", "manage_crop_templates"],
  "fallback": "safe_read_default",
  "schema_token_estimate": 620,
  "policy_violations": []
}
```

Admin-web debug JSON should include router diagnostics together with messages, pending plans, and skill call input/output so failed conversations can be replayed.

## Evaluation

Add a Skill Router regression suite with curated cases from:

- Real failed sessions such as `tests/chat-session/session4.json` and `session5.json`.
- Each Skill's trigger and anti-trigger examples.
- High-risk write operations.
- Multi-intent farm workflows.

Metrics:

```text
Top-1 tool accuracy >= 90%
Top-3 tool recall >= 98%
Write-tool false exposure for read intents <= 1%
High-risk write false exposure = 0
Normal query selected_tools <= 2
Complex query selected_tools <= 5
No selected_tools > 10 in production traces
Normal query total token reduction >= 50%
Rule/catalog router p95 < 50ms
Light classifier fallback p95 < 800ms
Multi-intent step recall >= 90%
Pending execution dropped-step count = 0
```

Required acceptance cases:

- `session5`: "我家有哪些作物栽种" selects `get_farm_status` or `get_crop_cycle_info`, with `selected_tools <= 2`.
- `session4`: worker creation plus harvest assignment becomes a two-step plan.
- Work order labor payable amount is 100 when the utterance or worker profile states daily wage 100.
- Final answer after tool result does not rebind 33 tools.
- All write operations still require confirmation.

## Rollout Plan

### Milestone 1: Router Token Stop-Loss

1. Add catalog models and router decision types.
2. Build catalog from current Skill metadata plus a small registry file for missing fields.
3. Replace `fallback_all` with safe defaults and clarification.
4. Integrate router decision into runtime tool binding and ContextPolicy.
5. Disable tool rebinding in final answer rounds unless router explicitly requests a follow-up read.
6. Add router trace nodes and regression cases for `session5`.

Exit criteria: no normal production trace exposes more than 5 tools, and `session5` selects at most 2 tools.

### Milestone 2: Multi-Intent Write Safety

1. Add persistent pending plan tables.
2. Add compatibility adapter for existing single pending actions.
3. Support batch confirmation for low and medium risk action plans.
4. Add labor wage fallback rules for work order creation.
5. Add regression cases for `session4`.

Exit criteria: the worker-plus-work-order session creates a two-step pending plan, and work order labor payable amount never defaults to zero unless explicitly requested.

### Milestone 3: Retrieval and Continuous Evaluation

1. Add optional hybrid retrieval over Skill Catalog examples and anti-examples.
2. Add router token distribution reports.
3. Add admin debug export fields for router decisions and pending plans.
4. Expand evaluation coverage from real conversations and Skill examples.

Exit criteria: router evaluation reports Top-1 accuracy, Top-3 recall, false write exposure, selected tool distribution, and token reduction metrics.

## Non-Goals

- Do not replace all existing Skill implementations.
- Do not remove confirmation for write operations.
- Do not introduce autonomous destructive actions.
- Do not require embedding retrieval for the first milestone if catalog rules already meet acceptance criteria.
