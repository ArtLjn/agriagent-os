## 1. Regression First

- [x] 1.1 Add PlanDraft model serialization tests for direct reply, read plan, single write, multi-step write, and clarification route types.
- [x] 1.2 Add adapter regression tests that convert existing RouterDecision into PlanDraft without breaking selected_tools compatibility.
- [x] 1.3 Add validator regression tests for missing required fields, empty write params, uniquely inferable default wage, and ambiguous wage clarification.
- [x] 1.4 Add pending action and pending plan regression tests proving both are derived from validated PlanDraft steps.
- [x] 1.5 Add reflection regression tests for no-tool success claims that reference PlanDraft evidence.
- [x] 1.6 Add evaluation and diagnostics regression tests for planning, validation, selection, pending creation, execution, and response-quality stages.

## 2. PlanDraft Contract And Adapter

- [x] 2.1 Create PlanDraft, PlanStep, PlanValidationResult, PlanIssue, and route type models in a focused Agent planning module.
- [x] 2.2 Implement RouterDecision-to-PlanDraft adapter using existing intent frames, selected tools, params hints, semantic evidence, and missing fields.
- [x] 2.3 Preserve existing RouterDecision outputs during migration while adding PlanDraft trace payload.
- [x] 2.4 Add trace serialization that redacts sensitive data and keeps PlanDraft compact for debug export.

## 3. Domain Validator

- [x] 3.1 Implement validator for read plans, direct replies, single write steps, and multi-step write plans.
- [x] 3.2 Validate required params and reject empty write step params before pending creation.
- [x] 3.3 Resolve uniquely inferable worker default wage and record inferred fields with source metadata.
- [x] 3.4 Downgrade ambiguous or incomplete write drafts to clarification with missing field reasons.
- [x] 3.5 Keep validator independent from individual Skill implementations; use Skill metadata and domain lookup helpers.

## 4. Runtime Integration

- [x] 4.1 Add a PlanDraft creation stage after conversation intake and before LLM tool binding.
- [x] 4.2 Convert existing single-write pending action creation to consume validated PlanDraft when available.
- [x] 4.3 Convert existing multi-write pending plan creation to consume validated PlanDraft when available.
- [x] 4.4 Keep fallback path to current RouterDecision/tool-call behavior while migration is incomplete.
- [x] 4.5 Ensure greetings, safe direct replies, and ordinary read queries do not pay the cost of unnecessary LLM planning.

## 5. Reflection And Diagnostics

- [x] 5.1 Extend Reflection checks to inspect PlanDraft route type, validation result, and pending creation evidence.
- [x] 5.2 Include PlanDraft evidence in `reflection_check` traces for no-tool success claim blocks.
- [x] 5.3 Extend skill diagnostics to expose PlanDraft summary, validation status, missing fields, inferred fields, and failure stage.
- [x] 5.4 Ensure Data Flywheel repair packs can include PlanDraft and validation evidence in debug exports.

## 6. Evaluation

- [x] 6.1 Extend skill regression cases to assert PlanDraft planning coverage for implicit farm labor work.
- [x] 6.2 Extend evaluation reports with stage-level failure counts or labels for planning, validation, selection, pending creation, execution, and response quality.
- [x] 6.3 Verify semantic planning failures are not reported only as generic bad replies.

## 7. Documentation And Validation

- [x] 7.1 Update Agent architecture docs to show Conversation Intake -> PlanDraft -> Validator -> Pending/Read/Reply -> Reflection.
- [x] 7.2 Document that Rule Gate is a safety/evidence layer, not the long-term semantic parser.
- [x] 7.3 Run focused backend tests for planning, router adapter, validator, pending, reflection, diagnostics, and evaluation.
- [x] 7.4 Run `openspec validate introduce-agent-plan-draft-pipeline --strict`.
- [x] 7.5 Summarize unsupported scenarios: destructive multi-step plans, ambiguous historical updates, and write plans requiring external real-time data without evidence.

Unsupported scenarios documented in architecture notes: destructive multi-step plans stay clarification-first; ambiguous historical updates require user confirmation; write plans that depend on external real-time data without evidence must not auto-create pending actions.
