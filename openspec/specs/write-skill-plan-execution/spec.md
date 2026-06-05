## Purpose

定义 write-skill-plan-execution 能力的行为要求。

## Requirements

### Requirement: Write skills use Plan-Then-Execute flow
All write operation skills SHALL follow a Plan-Then-Execute pattern: the LLM generates a plan (intent + parameters), an orchestrator validates the plan, the user confirms, and only then the write operation executes.

#### Scenario: Normal write operation with confirmation
- **WHEN** the user says "昨天买了200块化肥"
- **THEN** the LLM SHALL generate a plan: {"intent": "create_cost_record", "params": {"amount": 200, "category": "化肥"}}
- **AND** the system SHALL generate a pending action with a confirmation message
- **AND** the user SHALL be able to review the plan before execution
- **AND** only after user confirmation SHALL the database record be created

#### Scenario: User rejects the plan
- **WHEN** a pending action is generated for "昨天买了200块化肥"
- **AND** the user says "不对，是300块"
- **THEN** the system SHALL cancel the pending action
- **AND** the LLM SHALL receive the correction and generate a new plan
- **AND** the new pending action SHALL reflect the corrected amount of 300

### Requirement: Plan validation by orchestrator
Before generating a pending action, the system SHALL validate the plan: check parameter completeness, validate against schema constraints, and verify the user has permission to perform the operation.

#### Scenario: Invalid plan blocked by orchestrator
- **WHEN** the LLM generates a plan with missing `amount`
- **THEN** the orchestrator SHALL reject the plan
- **AND** the LLM SHALL receive the validation error
- **AND** the LLM SHALL self-correct before any pending action is shown to the user

#### Scenario: Valid plan passes orchestrator
- **WHEN** the LLM generates a plan with all required parameters and valid values
- **THEN** the orchestrator SHALL approve the plan
- **AND** the system SHALL proceed to generate the pending action
