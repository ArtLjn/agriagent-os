## ADDED Requirements

### Requirement: Registered Skill selection coverage
The system SHALL ensure every enabled registered Skill has an explicit selection path.

#### Scenario: Work order creation selected
- **WHEN** the user says "今天东大棚4个工人给西瓜授粉，每人200，先付老王200"
- **THEN** tool selection SHALL include `create_operation_work_order`
- **AND** the Agent SHALL enter the write confirmation flow

#### Scenario: Labor payable query selected
- **WHEN** the user says "老王还欠多少人工钱"
- **THEN** tool selection SHALL include `get_labor_payables`
- **AND** the Agent SHALL prefer the labor payable query Skill over generic cost summary

#### Scenario: Work order update selected
- **WHEN** the user says "刚才那条授粉记录不是付老王，是付老李200"
- **THEN** tool selection SHALL include `update_operation_work_order`
- **AND** the Agent SHALL create a pending action after target resolution

#### Scenario: Labor settlement selected
- **WHEN** the user says "给老王补付300人工"
- **THEN** tool selection SHALL include `settle_labor_payment`
- **AND** the Agent SHALL create a pending action showing affected labor entries

### Requirement: Selection audit parity with registry
The system SHALL provide a selection audit that compares registered enabled Skills with selector and chain policy coverage.

#### Scenario: Registered Skill omitted from selector
- **WHEN** a registered enabled Skill has no selector rule, classifier target, or declared fallback path
- **THEN** the audit SHALL report the Skill name and fail CI

#### Scenario: Disabled Skill omitted intentionally
- **WHEN** a Skill is registered but disabled by configuration
- **THEN** selector SHALL NOT return it
- **AND** the audit SHALL treat the omission as valid only if the disabled reason is declared
