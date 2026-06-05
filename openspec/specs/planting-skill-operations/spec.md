# planting-skill-operations Specification

## Purpose
TBD - created by archiving change enhance-agent-skill-capabilities. Update Purpose after archive.
## Requirements
### Requirement: Crop cycle update Skill
The system SHALL provide an `update_crop_cycle` Skill that lets the Agent modify an existing crop cycle's start date, season, name, area, status, current stage, or note after user confirmation.

#### Scenario: Modify corn cycle start date
- **WHEN** the user says "修改玉米茬口9月1开始" and exactly one active corn cycle exists with start date 2026-06-05
- **THEN** the Agent creates a pending action to update that crop cycle start date from 2026-06-05 to 2026-09-01
- **AND** the Agent does not ask whether to create a new crop cycle

#### Scenario: Multiple matching crop cycles need clarification
- **WHEN** the user says "修改玉米茬口9月1开始" and multiple corn cycles are active or recently planned
- **THEN** the Agent asks the user to choose the target crop cycle before creating a pending action

### Requirement: Operation work order query Skill
The system SHALL provide a read Skill for querying operation work orders by crop cycle, unit, operation type, worker, date range, and payment status.

#### Scenario: Query recent pollination work
- **WHEN** the user asks "最近玉米授粉作业有哪些"
- **THEN** the Agent calls the work order query Skill and returns matching work orders with date, scope, workers, and payment summary

### Requirement: Operation work order update Skill
The system SHALL provide an update Skill for modifying work order date, operation type, scope, note, workers, payable amount, and paid amount after user confirmation.

#### Scenario: Correct paid worker
- **WHEN** the user says "刚才那条授粉记录不是付老王，是付老李200"
- **THEN** the Agent creates a pending action that updates the latest matching work order labor payment from 老王 to 老李

### Requirement: Labor payable query Skill
The system SHALL provide a read Skill for querying unpaid labor by worker, crop cycle, work order, date range, and farm.

#### Scenario: Query unpaid labor by worker
- **WHEN** the user asks "老王还欠多少人工钱"
- **THEN** the Agent calls the labor payable query Skill and returns payable, paid, unpaid amount, and related work orders

### Requirement: Labor payment settlement Skill
The system SHALL provide a write Skill for settling or partially paying labor entries after user confirmation.

#### Scenario: Partial labor payment
- **WHEN** the user says "给老王补付300人工"
- **THEN** the Agent creates a pending action that pays 300 toward 老王's unpaid labor entries and shows the affected entries before execution

