# skill-regression-evaluation Specification

## Purpose
TBD - created by archiving change enhance-agent-skill-capabilities. Update Purpose after archive.
## Requirements
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

### Requirement: Registered Skill regression coverage gate
The evaluation suite SHALL verify that every enabled registered Skill has at least one regression case for selection and one domain-appropriate case for execution or rejection.

#### Scenario: Enabled Skill without case
- **WHEN** a registered enabled Skill has no regression case
- **THEN** the evaluation report SHALL mark it `coverage_missing`
- **AND** CI SHALL fail for production-ready Skills

#### Scenario: Admin Skill rejection case
- **WHEN** a Skill declares `permission_level=admin`
- **THEN** the regression suite SHALL include a non-admin rejection case
- **AND** if admin execution is enabled, an admin success case

#### Scenario: External network disabled case
- **WHEN** a Skill declares `permission_level=external_network`
- **THEN** the regression suite SHALL include a disabled-provider case that performs no real network access

### Requirement: Coverage report by exposure status
The evaluation report SHALL aggregate Skill coverage by exposure status from the coverage matrix.

#### Scenario: Matrix status reported
- **WHEN** the evaluation report is generated
- **THEN** it SHALL include counts for `covered_by_skill`, `needs_skill`, `admin_skill`, `forbidden_for_llm`, and `no_skill_required`
- **AND** it SHALL list high-priority `needs_skill` entries

### Requirement: Selection and execution split
Skill regression SHALL report selection coverage separately from execution coverage.

#### Scenario: Skill selected but not executed
- **WHEN** selector includes `settle_labor_payment`
- **AND** Tool Executor rejects it because required parameters are missing
- **THEN** evaluation SHALL mark selection as covered
- **AND** execution as failed with a parameter or confirmation classification

