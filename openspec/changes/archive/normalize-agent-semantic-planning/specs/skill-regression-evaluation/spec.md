## MODIFIED Requirements

### Requirement: Skill regression case set
The system SHALL maintain regression cases for Skill selection, parameter extraction, confirmation flow, execution result, and response quality. The case set SHALL include high-risk semantic planning cases for implicit writes, multi-intent writes, farm operation labor records, and no-tool write success claims.

#### Scenario: Regression case for crop cycle update
- **WHEN** the regression suite runs the case "修改玉米茬口9月1开始"
- **THEN** the expected Skill is `update_crop_cycle`, the expected target is the active corn cycle, and the expected `start_date` is 2026-09-01

#### Scenario: Regression case for implicit farm labor work
- **WHEN** the regression suite runs the case "李海这个月干了15天压瓜"
- **THEN** the expected routing outcome SHALL be `create_operation_work_order` or clarification for missing fields
- **AND** the forbidden outcome SHALL include direct success text without pending action or tool call

#### Scenario: Regression case for worker extraction boundary
- **WHEN** the regression suite runs the case "今天李海去6号棚压蔓工资100一天"
- **THEN** the expected worker SHALL be "李海"
- **AND** the expected planting unit SHALL be "6号棚"
- **AND** the forbidden worker SHALL be "号棚压蔓"

#### Scenario: Regression case for deterministic multi-step write
- **WHEN** the regression suite runs the case "新来一个工人李丽工资100一天，今天去6号棚收水稻"
- **THEN** the expected pending plan SHALL include `manage_workers` and `create_operation_work_order`
- **AND** the work order step SHALL depend on the worker creation step

### Requirement: Selection and execution split
Skill regression SHALL report selection coverage separately from execution coverage, and SHALL separately report semantic planning, pending creation, and final-response guard outcomes for write-like user inputs.

#### Scenario: Skill selected but not executed
- **WHEN** selector includes `settle_labor_payment`
- **AND** Tool Executor rejects it because required parameters are missing
- **THEN** evaluation SHALL mark selection as covered
- **AND** execution as failed with a parameter or confirmation classification

#### Scenario: Semantic planning caught write but pending was not created
- **WHEN** Semantic Gate identifies a write-like input
- **AND** no pending action or pending plan is created
- **THEN** evaluation SHALL report whether the system asked clarification or incorrectly returned success
- **AND** incorrect success SHALL be labeled as a failure

## ADDED Requirements

### Requirement: Repair pack drafts include actionable assertions
When Data Flywheel exports repair packs for semantic planning, pending, hallucinated execution, or tool result state failures, generated regression drafts SHALL include issue assertions when evidence is available.

#### Scenario: No-tool success claim creates assertion
- **WHEN** a repair pack case contains user input "李海这个月干了15天压瓜"
- **AND** the assistant reply contains "已为您记录"
- **AND** debug evidence shows no tool call or pending plan
- **THEN** the regression draft SHALL include an issue assertion for hallucinated execution or tool result state
- **AND** `regression_ready` MAY become true if expected behavior is unambiguous
