## ADDED Requirements

### Requirement: Reflection consumes PlanDraft evidence
Reflection SHALL inspect PlanDraft route type, validation result, selected tools, pending creation evidence, and tool results before approving final replies.

#### Scenario: No-tool success claim blocked with draft evidence
- **WHEN** PlanDraft indicates a write-like or clarification-needed input
- **AND** no pending action, pending plan, or successful write tool result exists
- **AND** the final reply claims "已记录" or equivalent write success
- **THEN** Reflection SHALL block or replace the reply
- **AND** the trace SHALL include PlanDraft evidence for the block

#### Scenario: Valid pending confirmation passes
- **WHEN** PlanDraft validation passes
- **AND** pending action is created with matching confirmation context
- **THEN** Reflection SHALL allow the pending confirmation reply

### Requirement: Reflection failure reason is stage-aware
When Reflection blocks a response, the system SHALL indicate whether the failure came from planning, validation, pending creation, execution, or response quality.

#### Scenario: Response-quality failure is labeled
- **WHEN** the final reply contradicts PlanDraft or tool evidence
- **THEN** the diagnostic output SHALL label the failure stage as `response_quality`
