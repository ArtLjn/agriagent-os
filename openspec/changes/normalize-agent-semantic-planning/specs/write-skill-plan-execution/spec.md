## MODIFIED Requirements

### Requirement: Write skills use Plan-Then-Execute flow
All write operation skills SHALL follow a Plan-Then-Execute pattern: the LLM or Semantic Gate generates a plan (intent + parameters), an orchestrator validates the plan, Reflection checks write risk and plan consistency, the user confirms, Reflection re-checks the pending plan before execution, and only then the write operation executes. Multi-intent write inputs SHALL create a pending plan only when required fields are present or uniquely inferable.

#### Scenario: Normal write operation with confirmation
- **WHEN** the user says "昨天买了200块化肥"
- **THEN** the LLM SHALL generate a plan: {"intent": "create_cost_record", "params": {"amount": 200, "category": "化肥"}}
- **AND** the system SHALL validate the plan and run Reflection checks before showing it
- **AND** the system SHALL generate a pending action with a confirmation message
- **AND** the user SHALL be able to review the plan before execution
- **AND** only after user confirmation and pre-execution Reflection pass SHALL the database record be created

#### Scenario: User rejects the plan
- **WHEN** a pending action is generated for "昨天买了200块化肥"
- **AND** the user says "不对，是300块"
- **THEN** the system SHALL cancel the pending action
- **AND** the LLM SHALL receive the correction and generate a new plan
- **AND** the new pending action SHALL reflect the corrected amount of 300

#### Scenario: Deterministic worker plus work order creates pending plan
- **WHEN** the user says "新来一个工人李丽工资100一天，今天去6号棚收水稻"
- **THEN** the system SHALL generate a pending plan with `manage_workers` before `create_operation_work_order`
- **AND** the work order step SHALL depend on the worker creation step
- **AND** the confirmation text SHALL show both steps before execution

#### Scenario: Operation plus labor can be one pending action
- **WHEN** the user says "今天李海去6号棚压蔓工资100一天"
- **THEN** the system SHALL generate a pending action for `create_operation_work_order`
- **AND** the pending parameters SHALL include worker "李海", planting unit "6号棚", operation type "压蔓", and unit price 100
- **AND** the pending action SHALL NOT execute before user confirmation

### Requirement: Plan validation by orchestrator
Before generating a pending action or pending plan, the system SHALL validate the plan: check parameter completeness, validate against schema constraints, verify the user has permission to perform the operation, and require Reflection to approve write-risk and confirmation consistency. Invalid or incomplete plans SHALL be converted to clarification rather than shown as executable confirmation.

#### Scenario: Invalid plan blocked by orchestrator
- **WHEN** the LLM generates a plan with missing `amount`
- **THEN** the orchestrator SHALL reject the plan
- **AND** the LLM SHALL receive the validation error
- **AND** the LLM SHALL self-correct before any pending action is shown to the user

#### Scenario: Valid plan passes orchestrator
- **WHEN** the LLM generates a plan with all required parameters and valid values
- **THEN** the orchestrator SHALL approve the plan
- **AND** Reflection SHALL approve the plan consistency and write risk
- **AND** the system SHALL proceed to generate the pending action

#### Scenario: Reflection blocks inconsistent confirmation
- **WHEN** the LLM generates a write plan for amount 200
- **AND** the confirmation message shown to the user says amount 300
- **THEN** Reflection SHALL block the pending action
- **AND** the system SHALL NOT ask the user to confirm the inconsistent plan

#### Scenario: Missing operation field asks clarification
- **WHEN** the user says "李海这个月干了15天"
- **THEN** the orchestrator SHALL NOT create a pending action or pending plan
- **AND** the system SHALL ask for the missing operation type
- **AND** the system SHALL NOT claim that the work was recorded

#### Scenario: Empty write step is blocked
- **WHEN** a pending plan candidate contains a write step with empty params
- **THEN** Reflection or orchestrator SHALL block the plan
- **AND** the user SHALL receive a clarification or safe retry message
