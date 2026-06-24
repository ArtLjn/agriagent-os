## ADDED Requirements

### Requirement: Pending creation derives from validated PlanDraft
The system SHALL create pending actions and pending plans from validated PlanDraft steps. It SHALL NOT create pending actions or pending plans from unvalidated or empty write parameters.

#### Scenario: Single write creates pending action from draft
- **WHEN** a validated PlanDraft has route type `write_pending_action`
- **THEN** the Tool Executor SHALL create exactly one pending action from the draft step
- **AND** the confirmation context SHALL include validation and inference evidence

#### Scenario: Multi-step write creates pending plan from draft
- **WHEN** a validated PlanDraft has route type `write_pending_plan`
- **THEN** the Tool Executor SHALL create a pending plan from ordered draft steps
- **AND** step dependencies SHALL match the PlanDraft

#### Scenario: Empty write step is blocked
- **WHEN** a PlanDraft write step has empty params
- **THEN** validation SHALL block pending creation
- **AND** the user SHALL receive a clarification or safe retry message

### Requirement: Domain Validator resolves inferable context
Before pending creation, the Domain Validator SHALL resolve uniquely inferable domain context such as worker default wage, worker identity, planting unit, and active cycle when existing policy allows inference.

#### Scenario: Worker default wage is inferred
- **WHEN** a write draft references one existing worker with a default daily wage
- **AND** the user provided quantity but did not provide unit price
- **THEN** the validator SHALL infer unit price from the worker profile
- **AND** the pending confirmation SHALL show the inference source

#### Scenario: Ambiguous default wage asks clarification
- **WHEN** a write draft references multiple possible workers or no default wage
- **THEN** the validator SHALL NOT guess a wage
- **AND** pending creation SHALL be blocked until the user clarifies
