## Why

Current Agent routing is still split across classifier frames, tool selection, pending action, pending plan, and reflection. This lets targeted fixes work, but it does not yet give every turn a single explainable planning contract, so long-term semantic coverage can drift into scattered rules and skill-specific patches.

This change introduces a system-level PlanDraft pipeline so ordinary chat, read queries, single writes, multi-step writes, and clarifications all pass through one lightweight planning and validation contract before execution or response.

## What Changes

- Introduce a `PlanDraft` / `PlanStep` / `PlanValidationResult` contract for Agent turns.
- Add a PlanDraft pipeline stage between conversation intake and tool execution.
- Normalize routing outcomes into one of: `direct_reply`, `read_plan`, `write_pending_action`, `write_pending_plan`, or `clarification`.
- Move cross-skill write completeness checks into a Domain Validator instead of spreading them across individual skill patches.
- Keep the main chat path as a single master Agent; this does not introduce autonomous multi-agent execution.
- Keep lightweight rules as a Rule Gate, but make them input evidence for PlanDraft rather than the long-term semantic parser.
- Extend diagnostics and evaluation to report planning, validation, pending creation, execution, and response-quality stages separately.

## Capabilities

### New Capabilities

- `agent-plan-draft-pipeline`: Defines the system-level planning contract, lifecycle, validation states, and route outcomes for every Agent turn.

### Modified Capabilities

- `agent-intent-router`: Router output becomes evidence feeding PlanDraft rather than the final planning contract.
- `write-skill-plan-execution`: Pending action and pending plan are derived from validated PlanDraft steps.
- `agent-reflection-control`: Reflection reads PlanDraft and validation evidence when blocking unsafe final replies.
- `skill-regression-evaluation`: Evaluation reports planning, validation, pending, execution, and response-quality outcomes separately.
- `agent-skill-diagnostics`: Diagnostics exposes PlanDraft, validation result, and failure stage for trace/debug export.

## Impact

- Affected code:
  - `backend/app/agent/router/**`
  - `backend/app/agent/runtime/**`
  - `backend/app/agent/reflector/**`
  - `backend/app/infra/pending_actions.py`
  - `backend/app/infra/pending_action_presenter.py`
  - `backend/app/evaluation/**`
  - related Agent, router, pending, reflection, and evaluation tests
- No new external dependency is required.
- No HTTP API breaking change is intended.
- Existing Skill implementations remain atomic; skills do not call each other.
- Write operations still require user confirmation before execution.
