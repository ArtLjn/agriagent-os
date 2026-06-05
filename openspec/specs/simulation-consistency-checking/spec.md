## Purpose

定义 simulation-consistency-checking 能力的行为要求。

## Requirements

### Requirement: Distinguish hallucination from execution failure
The consistency checker SHALL detect when a skill was actually invoked (via trace evidence) but the database write failed, reporting this as `execution_failure` rather than `hallucination`.

#### Scenario: Skill invoked but DB write failed
- **WHEN** the Agent trace shows a `skill_call` node for `create_cost_record` was executed
- **AND** the database `cost_records` table shows no new records
- **AND** the LLM reply contains success keywords ("已记账")
- **THEN** the error SHALL be classified as `execution_failure: skill 已调用但数据库写入失败`
- **AND** NOT as `hallucination`

#### Scenario: True hallucination
- **WHEN** no `skill_call` trace node exists for the claimed operation
- **AND** the database shows no changes
- **THEN** the error SHALL be classified as `hallucination`

### Requirement: Substring matching for match_fields
When verifying `expected_db_changes.match_fields`, the system SHALL use substring matching for string fields and exact matching for numeric/boolean fields.

#### Scenario: Substring match for category
- **WHEN** a test case expects `match_fields.category = "番茄"`
- **AND** the actual database record has `category = "番茄销售"`
- **THEN** the match SHALL be considered successful

#### Scenario: Exact match for amount
- **WHEN** a test case expects `match_fields.amount = 200`
- **AND** the actual database record has `amount = 200.0`
- **THEN** the match SHALL be considered successful (numeric tolerance)

#### Scenario: Exact match failure
- **WHEN** a test case expects `match_fields.amount = 200`
- **AND** the actual database record has `amount = 300`
- **THEN** the match SHALL fail with `state_mismatch`

### Requirement: Cancel operation detection
When a test case expects no database changes (empty `expected_db_changes`) and receives a pending action, the system SHALL send a cancel message and verify that no database changes occurred.

#### Scenario: Cancel pending action
- **WHEN** a test case has `expected_db_changes = {}`
- **AND** the Agent returns a pending action
- **THEN** the system SHALL send a cancel message
- **AND** the database SHALL remain unchanged
- **AND** the result SHALL be marked as passed (no hallucination error)

### Requirement: Expected change count verification
The system SHALL verify that the number of added records in each table matches the `added` count specified in `expected_db_changes`.

#### Scenario: Count mismatch
- **WHEN** a test case expects `cost_records.added = 1`
- **AND** the actual snapshot shows 0 added records
- **THEN** the system SHALL report `state_mismatch: 表 cost_records 预期新增 1 条，实际新增 0 条`
