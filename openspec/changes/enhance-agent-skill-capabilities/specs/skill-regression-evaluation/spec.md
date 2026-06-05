## ADDED Requirements

### Requirement: Skill regression case set
The system SHALL maintain regression cases for Skill selection, parameter extraction, confirmation flow, execution result, and response quality.

#### Scenario: Regression case for crop cycle update
- **WHEN** the regression suite runs the case "修改玉米茬口9月1开始"
- **THEN** the expected Skill is `update_crop_cycle`, the expected target is the active corn cycle, and the expected `start_date` is 2026-09-01

### Requirement: Confirmation flow evaluation
Evaluation SHALL verify pending action creation, confirmation execution, correction handling, cancellation handling, and timeout behavior.

#### Scenario: User corrects pending action
- **WHEN** a pending action proposes amount 200 and the user replies "不对，是300"
- **THEN** the evaluation records whether the original pending action is cancelled and a corrected pending action with amount 300 is created

### Requirement: Database consistency evaluation
Evaluation SHALL compare database snapshots before and after confirmed write Skill execution to verify actual business changes.

#### Scenario: Claimed write without database change
- **WHEN** the Agent claims a crop cycle was updated but the database snapshot is unchanged
- **THEN** the evaluation marks the case as `execution_inconsistency`

### Requirement: Skill coverage report
The evaluation report SHALL show coverage by Skill, business domain, permission level, confirmation path, and context dependency.

#### Scenario: Missing coverage for new Skill
- **WHEN** a registered write Skill has no regression case
- **THEN** the report marks the Skill as `coverage_missing`
