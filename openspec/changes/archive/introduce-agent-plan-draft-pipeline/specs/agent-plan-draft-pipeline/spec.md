## ADDED Requirements

### Requirement: Agent turns produce a PlanDraft
The system SHALL normalize every Agent turn into a `PlanDraft` before deciding whether to answer directly, bind read tools, create a pending action, create a pending plan, or ask clarification.

#### Scenario: Greeting creates direct reply draft
- **WHEN** the user says "你好"
- **THEN** the system SHALL create a PlanDraft with route type `direct_reply`
- **AND** the system SHALL NOT require tool binding or pending creation

#### Scenario: Read query creates read plan draft
- **WHEN** the user says "我的工人有哪些"
- **THEN** the system SHALL create a PlanDraft with route type `read_plan`
- **AND** the draft SHALL include the selected read Skill evidence

#### Scenario: Single write creates pending action draft
- **WHEN** the user says "今天李海去6号棚压蔓工资100一天"
- **THEN** the system SHALL create a PlanDraft with route type `write_pending_action`
- **AND** the draft SHALL include a single write step for `create_operation_work_order`

#### Scenario: Multi-step write creates pending plan draft
- **WHEN** the user says "新来一个工人李丽工资100一天，今天去6号棚收水稻"
- **THEN** the system SHALL create a PlanDraft with route type `write_pending_plan`
- **AND** the draft SHALL include ordered steps for `manage_workers` and `create_operation_work_order`

#### Scenario: Missing required field creates clarification draft
- **WHEN** the user says "李海这个月干了15天"
- **THEN** the system SHALL create a PlanDraft with route type `clarification`
- **AND** the draft SHALL include `operation_type` in missing fields

### Requirement: PlanDraft validation is explicit
The system SHALL validate PlanDraft before any pending action, pending plan, or tool execution is created. Validation SHALL produce a `PlanValidationResult` with status, blocking issues, missing fields, and inferred fields.

#### Scenario: Valid write draft passes validation
- **WHEN** a PlanDraft contains a write step with required operation type, worker, quantity, and wage policy
- **THEN** validation SHALL pass
- **AND** pending creation MAY proceed

#### Scenario: Invalid write draft becomes clarification
- **WHEN** a PlanDraft contains a write step missing a required operation type
- **THEN** validation SHALL block pending creation
- **AND** the route type SHALL become `clarification`

#### Scenario: Default wage inference is recorded
- **WHEN** validation resolves a worker default wage for a labor write step
- **THEN** validation SHALL record the inferred unit price and source
- **AND** the confirmation context SHALL show that the wage came from the worker profile

### Requirement: PlanDraft remains single-agent runtime data
The system SHALL implement PlanDraft inside the existing master Agent runtime and SHALL NOT require autonomous multi-agent coordination for normal chat routing.

#### Scenario: Normal write does not spawn subagents
- **WHEN** the user says "昨天买了200块化肥"
- **THEN** the system SHALL produce and validate a PlanDraft in the main Agent path
- **AND** it SHALL NOT require a separate planner Agent or reviewer Agent
