## ADDED Requirements

### Requirement: Semantic Gate identifies high-risk business writes
The system SHALL run a lightweight Semantic Gate before final tool binding to identify user inputs that imply business data changes even when explicit write verbs are absent.

#### Scenario: Implicit labor work record is detected
- **WHEN** the user says "李海这个月干了15天压瓜"
- **THEN** the Semantic Gate SHALL classify the input as a write-intent business statement
- **AND** it SHALL produce intent frames for farm operation and labor usage
- **AND** the request SHALL NOT be treated as chitchat or no-tool fallback

#### Scenario: Ordinary statement is not forced into write flow
- **WHEN** the user says "李海最近挺忙的"
- **THEN** the Semantic Gate SHALL NOT create a write-intent frame
- **AND** the system MAY answer normally or ask a clarification question

### Requirement: Semantic Gate extracts farm labor plan hints
For farm labor statements, the system SHALL extract stable plan hints for worker, operation type, labor quantity, pay type, payment state, and time expression when present.

#### Scenario: Extracts worker operation and quantity
- **WHEN** the user says "李海这个月干了15天压瓜"
- **THEN** the plan hints SHALL include `worker_name=李海`
- **AND** the plan hints SHALL include `operation_type=压瓜`
- **AND** the plan hints SHALL include `quantity=15`
- **AND** the plan hints SHALL include `pay_type=daily`
- **AND** the plan hints SHALL include a natural period expression for "这个月"

#### Scenario: Does not confuse field name with worker name
- **WHEN** the user says "今天李海去6号棚压蔓工资100一天"
- **THEN** the extracted worker name SHALL be "李海"
- **AND** the extracted planting unit SHALL be "6号棚"
- **AND** the extracted operation type SHALL be "压蔓"
- **AND** the worker name SHALL NOT be "号棚压蔓"

### Requirement: Semantic Gate chooses clarify over unsafe plan
When a high-risk write input lacks required information that cannot be uniquely inferred from context, the system SHALL ask for clarification instead of generating an executable pending plan with empty or guessed parameters.

#### Scenario: Missing operation type asks clarification
- **WHEN** the user says "李海这个月干了15天"
- **THEN** the system SHALL ask which operation or work type should be recorded
- **AND** it SHALL NOT create a pending action
- **AND** it SHALL NOT reply that the work has been recorded

#### Scenario: Missing wage policy may still create work order if default wage is available
- **WHEN** the user says "李海这个月干了15天压瓜"
- **AND** exactly one active worker named "李海" exists with a default daily wage
- **THEN** the system MAY create a pending action or pending plan using the worker default wage
- **AND** the confirmation text SHALL show that the wage was inferred from the worker profile

### Requirement: Main chat remains single-agent by default
The system SHALL keep the main chat path as a single master Agent with Skills, Semantic Gate, Pending, and Reflection. Multi-agent coordination SHALL NOT be required for normal chat routing or write confirmation.

#### Scenario: Normal write request stays in single-agent path
- **WHEN** the user says "昨天买了200块化肥"
- **THEN** the system SHALL use the existing single-Agent write Skill flow
- **AND** it SHALL NOT spawn or require multiple autonomous agents
