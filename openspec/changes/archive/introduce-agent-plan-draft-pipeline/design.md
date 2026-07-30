## Context

Farm Manager currently routes turns through RuleIntentClassifier, RouterPolicy, LLM tool binding, Tool Executor, Pending, and Reflection. This works for many explicit cases, but planning evidence is distributed across `IntentFrame.params_hint`, tool calls, pending context, and reflection metadata. As the system grows, adding more natural-language cases through localized regex patches will not scale.

The goal is not to make every turn expensive or multi-agent. The goal is to normalize every turn into a lightweight planning contract before deciding whether it should be a direct reply, a read plan, a pending write action, a pending write plan, or a clarification.

## Goals / Non-Goals

**Goals:**

- Introduce a system-level `PlanDraft` contract for all Agent turns.
- Separate evidence collection, semantic planning, domain validation, and execution selection.
- Make single write and multi-step write share the same validation path.
- Give Reflection and Data Flywheel a stable artifact to inspect.
- Keep the main chat path single-agent and low-latency.
- Reduce pressure to grow regex rules indefinitely.

**Non-Goals:**

- Do not introduce autonomous multi-agent execution into normal chat.
- Do not replace every existing Skill or pending flow in one step.
- Do not require LLM planning for greetings, safe direct replies, or obvious read/write cases when Rule Gate can create a valid draft.
- Do not let PlanDraft bypass write confirmation.
- Do not make skills call each other.

## Decisions

### Decision 1: Add PlanDraft as a contract, not a new Agent

PlanDraft is a structured object produced inside the current master Agent runtime. It is not an autonomous planner agent.

Minimal shape:

```text
PlanDraft
  turn_id/session_id/farm_id
  raw_user_input
  route_type: direct_reply | read_plan | write_pending_action | write_pending_plan | clarification
  intent_frames[]
  steps[]
  evidence
  missing_fields[]
  validation
  source: rule_gate | llm_structured_planner | hybrid
```

Rationale:

- Keeps latency and operational complexity low.
- Gives downstream systems one stable planning artifact.
- Allows gradual migration from existing router decisions.

Alternatives considered:

- Full LLM planner for every turn: better semantic breadth, higher cost and less deterministic for simple paths.
- Multi-agent planner/reviewer: useful offline, too heavy for normal chat.
- Keep patching router/classifier: low cost short term, poor long-term semantic maintainability.

### Decision 2: Rule Gate remains first-pass evidence, not the semantic ceiling

Existing rules remain valuable for safety gates, known high-frequency expressions, and negative routing. They should produce evidence into PlanDraft, not become the only semantic parser.

Planner selection:

| Input class | Planner source |
| --- | --- |
| Greeting/chitchat | Rule Gate direct reply draft |
| Clear read query | Rule Gate read draft |
| Clear single write | Rule Gate or current tool-call path converted to write draft |
| Ambiguous write | Rule Gate clarification draft |
| Complex/multi-intent natural language | LLM structured planner or hybrid draft |

Rule additions must remain paired with positive and negative tests.

### Decision 3: Domain Validator owns cross-skill completeness

PlanDraft validation should be centralized. Validator checks:

- required params for each planned step;
- permission and write confirmation requirement;
- whether referenced worker/unit/cycle/default wage can be uniquely resolved;
- whether a missing field should trigger clarification instead of pending;
- whether a step is safe as pending action or needs pending plan.

This avoids pushing business completeness rules into individual skill implementations.

### Decision 4: Pending action and pending plan are both derived from PlanDraft

The current split is:

- single write -> pending action;
- multi-write -> pending plan.

The new pipeline keeps those storage models but derives both from the same validated PlanDraft. This makes single-step and multi-step writes follow the same planning and validation semantics.

### Decision 5: Reflection reads plan evidence

Reflection should not infer intent only from selected tools or final text. It should inspect:

- `PlanDraft.route_type`;
- validation result;
- write/read risk;
- selected/executed tool evidence;
- pending action/plan creation evidence.

This strengthens no-tool success claim detection and makes failure explanations easier for Data Flywheel.

### Decision 6: Evaluation reports stage-level outcomes

Evaluation should report:

- planning;
- validation;
- selection;
- pending creation;
- execution;
- response quality.

This keeps failures actionable. A semantic planning miss should not be mixed with a tool execution failure.

## Risks / Trade-offs

- [Risk] Over-designing PlanDraft into a workflow engine -> Mitigation: keep PlanDraft as data; execution still happens in Tool Executor and Pending services.
- [Risk] Double-running router and planner during migration -> Mitigation: adapt RouterDecision into PlanDraft first, then gradually add structured planner only for complex cases.
- [Risk] LLM structured planner produces overconfident params -> Mitigation: Domain Validator remains authoritative and can downgrade to clarification.
- [Risk] Existing tests assume router decisions directly drive tools -> Mitigation: keep compatibility fields and add adapter tests before replacing call sites.
- [Risk] More trace data increases noise -> Mitigation: expose compact summaries in normal logs and detailed PlanDraft only in diagnostics/debug export.

## Migration Plan

1. Add PlanDraft models and adapter from existing RouterDecision.
2. Add Domain Validator for common write/read route types.
3. Convert pending action and pending plan creation to read validated PlanDraft where available.
4. Extend Reflection to inspect PlanDraft evidence.
5. Extend diagnostics and evaluation reports with plan and validation stages.
6. Add optional structured planner path for complex/multi-intent inputs.
7. Keep old router path behind compatibility adapter until tests cover the new path.

Rollback strategy:

- PlanDraft is additive during migration.
- Runtime can fall back to existing RouterDecision + tool binding path if PlanDraft validation fails unexpectedly.
- Pending storage and Skill execution contracts remain unchanged.

## Open Questions

- Whether the structured planner should run only after Rule Gate detects complexity, or also when Rule Gate returns no tools for business-like input.
- Whether PlanDraft should be persisted for every turn or only included in trace/debug export.
- How much of existing `params_hint` should remain once PlanDraft steps become the primary planning data.
