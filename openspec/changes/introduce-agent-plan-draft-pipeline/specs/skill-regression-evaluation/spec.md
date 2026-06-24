## ADDED Requirements

### Requirement: Skill regression evaluates PlanDraft stages
Skill regression SHALL evaluate planning, validation, selection, pending creation, execution, and response quality as separate stages.

#### Scenario: Semantic planning coverage
- **WHEN** regression runs "李海这个月干了15天压瓜"
- **THEN** the result SHALL report whether PlanDraft captured worker, operation type, quantity, and write risk

#### Scenario: Validation coverage
- **WHEN** regression runs "李海这个月干了15天"
- **THEN** the result SHALL report validation as blocked by missing operation type
- **AND** it SHALL distinguish this from tool selection failure

#### Scenario: Pending creation coverage
- **WHEN** regression runs "新来一个工人李丽工资100一天，今天去6号棚收水稻"
- **THEN** the result SHALL report whether a pending plan was created from the validated draft

#### Scenario: Response guard coverage
- **WHEN** regression sees a no-tool reply claiming "已记录"
- **THEN** the result SHALL report a response-quality failure

### Requirement: Evaluation reports PlanDraft failure stages
Evaluation reports SHALL include counts or labels for `planning`, `validation`, `selection`, `pending_creation`, `execution`, and `response_quality` failures.

#### Scenario: Stage counts included in report
- **WHEN** an evaluation report is generated
- **THEN** the report SHALL include stage-level failure coverage
- **AND** semantic planning misses SHALL NOT be grouped only as generic bad replies
