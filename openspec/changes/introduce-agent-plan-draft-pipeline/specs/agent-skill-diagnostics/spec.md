## ADDED Requirements

### Requirement: Diagnostics expose PlanDraft and validation summaries
Skill diagnostics SHALL expose PlanDraft route type, steps, evidence, missing fields, validation status, inferred fields, and failure stage.

#### Scenario: Debug export includes PlanDraft summary
- **WHEN** a trace is exported for an Agent turn
- **THEN** the diagnostic report SHALL include the PlanDraft summary
- **AND** sensitive values SHALL continue to be sanitized by existing debug export rules

#### Scenario: Missing field diagnostic is visible
- **WHEN** validation blocks a draft because `operation_type` is missing
- **THEN** diagnostics SHALL show the missing field
- **AND** the failure stage SHALL be `validation` or `planning` according to the blocker source

#### Scenario: Inferred wage diagnostic is visible
- **WHEN** validation infers a worker default wage
- **THEN** diagnostics SHALL include `unit_price_source=worker_default`
