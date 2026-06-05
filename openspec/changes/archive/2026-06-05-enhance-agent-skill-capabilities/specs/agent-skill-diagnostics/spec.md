## ADDED Requirements

### Requirement: Skill trace diagnostic report
The system SHALL generate a diagnostic report for an Agent request that explains selected tools, injected context, tool calls, pending actions, errors, and final response.

#### Scenario: Tool not called
- **WHEN** the user expected a Skill call but trace contains no `skill_call` node
- **THEN** the diagnostic report identifies whether the request bypassed the Agent, tool selection excluded the Skill, schema validation failed, or the LLM chose not to call a tool

### Requirement: Pending action diagnostic
The system SHALL diagnose pending action lifecycle issues including creation, replacement, confirmation, correction, cancellation, timeout, execution, and cache invalidation.

#### Scenario: Pending action lost
- **WHEN** a user confirms an operation but no pending action exists
- **THEN** the diagnostic report identifies whether the pending action timed out, was overwritten, was cancelled, or the backend restarted

### Requirement: Context dependency diagnostic
The system SHALL diagnose missing context dependencies for a Skill using ContextBundle trace data and Skill metadata.

#### Scenario: Missing active cycle context
- **WHEN** `update_crop_cycle` fails because no target crop cycle was available
- **THEN** the diagnostic report states whether active cycle context was not selected, selected but dropped by budget, or unavailable in the database

### Requirement: Evaluation-to-trace drilldown
Every failed Skill regression case SHALL link to trace evidence or simulated trace details that explain the failure.

#### Scenario: Parameter error drilldown
- **WHEN** a regression case fails because `start_date` is 2026-06-01 instead of 2026-09-01
- **THEN** the report links to the prompt, context blocks, tool call parameters, validation result, and final reply
