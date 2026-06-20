## Purpose

定义 simulation-test-execution 能力的行为要求。

## Requirements

### Requirement: Session isolation for background execution
The simulation test execution engine SHALL create an independent database session for the background task, separate from the FastAPI request context session.

#### Scenario: Background task uses fresh session
- **WHEN** a simulation run is started via POST /simulation/run
- **THEN** the background task `_execute_run` SHALL create a new `SessionLocal()` session
- **AND** construct a new `SimulationRunner` with the fresh session
- **AND** the request-level session SHALL NOT be used for `before`/`after` snapshots

### Requirement: Per-case data isolation
The system SHALL support cleaning specified tables before each test case execution, removing only records belonging to the test farm.

#### Scenario: Clean tables before execution
- **WHEN** a test case has `precondition.clean_tables = ["cost_records"]`
- **THEN** before taking the `before` snapshot, the system SHALL delete all `cost_records` where `farm_id` matches the test farm
- **AND** the `before` snapshot SHALL contain zero records for those tables

#### Scenario: No clean tables without explicit precondition
- **WHEN** a test case has no `precondition.clean_tables`
- **THEN** the system SHALL NOT delete any existing records
- **AND** the test runs against the current database state

### Requirement: Batch execution with rate limiting
The system SHALL execute test cases sequentially with a delay between each case to avoid triggering API rate limits.

#### Scenario: Sequential execution with delay
- **WHEN** running a batch of 3 test cases
- **THEN** case 1 SHALL execute first
- **AND** after case 1 completes, the system SHALL wait 6 seconds before starting case 2
- **AND** the total execution time SHALL be at least 12 seconds (2 delays between 3 cases)

### Requirement: Repair pack regression case 执行
Simulation SHALL 支持运行从 failure repair pack 生成或接受的 regression cases，并将运行结果与 `pack_id` 和 `source_sample_id` 关联。

#### Scenario: 运行 repair pack regression case
- **WHEN** 管理员或 vibecoding 触发 repair pack 的 regression cases
- **THEN** Simulation SHALL 执行关联 case
- **AND** 每条结果 SHALL 包含 `pack_id`、`source_sample_id`、`fix_target`、通过状态和失败断言

### Requirement: Simulation 结果回流修复包状态
Simulation SHALL 将 repair pack regression case 的结果提供给 Data Flywheel，用于判断 pack 是否可以标记为已修复。

#### Scenario: 所有关联 regression case 通过
- **WHEN** 一个 repair pack 的所有关联 regression cases 均通过
- **THEN** 系统 SHALL 允许管理员将该 repair pack 标记为已修复
- **AND** 系统 SHALL 显示对应验证摘要

#### Scenario: 任一关联 regression case 失败
- **WHEN** 一个 repair pack 的任一关联 regression case 失败
- **THEN** 系统 SHALL 禁止自动 resolve 关联 labels
- **AND** 系统 SHALL 将失败断言展示为继续修复依据
