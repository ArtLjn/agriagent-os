# agent-skill-diagnostics Specification

## Purpose
TBD - created by archiving change enhance-agent-skill-capabilities. Update Purpose after archive.
## Requirements
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

### Requirement: Skill non-call root cause classification
The diagnostic report SHALL classify why an expected Skill was not called.

#### Scenario: Selector excluded Skill
- **WHEN** a request expected `get_labor_payables`
- **AND** the selected tool set did not include `get_labor_payables`
- **THEN** diagnostics SHALL report root cause `selector_excluded`
- **AND** include the selected tool names and matching selector layer

#### Scenario: Skill disabled
- **WHEN** a request expected `web_search`
- **AND** `web_search` was disabled by configuration
- **THEN** diagnostics SHALL report root cause `skill_disabled`
- **AND** include the disabled reason

#### Scenario: Permission rejected
- **WHEN** LLM selected an admin Skill
- **AND** Tool Executor rejected it for a non-admin user
- **THEN** diagnostics SHALL report root cause `permission_rejected`
- **AND** include the required permission level

#### Scenario: Schema validation failed
- **WHEN** LLM selected a Skill but Tool Executor rejected its arguments
- **THEN** diagnostics SHALL report root cause `schema_validation_failed`
- **AND** include the validation error summary

### Requirement: Coverage matrix drilldown
Diagnostics SHALL link runtime failures to the coverage matrix entry for the affected capability.

#### Scenario: Missing Skill capability
- **WHEN** a user asks for a system function classified as `needs_skill`
- **THEN** diagnostics SHALL report that no Skill currently covers the capability
- **AND** identify the matrix entry and priority

