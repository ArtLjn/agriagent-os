## MODIFIED Requirements

### Requirement: Registered Skill selection coverage
The system SHALL ensure every enabled registered Skill has an explicit selection path. The router SHALL also recognize implicit farm operation and labor write inputs that do not contain explicit "记录" or "创建" verbs when they contain enough business evidence such as worker name, operation type, labor quantity, wage, or payment hints.

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

#### Scenario: Implicit farm labor work selects work order skill
- **WHEN** the user says "李海这个月干了15天压瓜"
- **THEN** tool selection SHALL include `create_operation_work_order` or produce a clarification for missing work-order fields
- **AND** the Agent SHALL NOT return a no-tool success reply

#### Scenario: Wage-only statement selects wage skill
- **WHEN** the user says "给李海记一笔15天压瓜工资，每天180"
- **THEN** tool selection SHALL include `manage_wages` or ask whether to create a work order
- **AND** the Agent SHALL NOT select `settle_labor_payment` unless the user asks to pay or settle wages

#### Scenario: Labor settlement wording selects settlement skill
- **WHEN** the user says "把李海这笔工资结了"
- **THEN** tool selection SHALL include `settle_labor_payment`
- **AND** the Agent SHALL NOT create a new wage entry

## ADDED Requirements

### Requirement: Router exposes semantic planning evidence
When the router identifies a high-risk write or multi-intent input, it SHALL expose structured evidence in the route decision trace so Data Flywheel and regression tests can explain why the input was routed or clarified.

#### Scenario: Route trace includes semantic evidence
- **WHEN** the user says "李海这个月干了15天压瓜"
- **THEN** the route trace SHALL include semantic evidence for worker, operation type, quantity, and write risk
- **AND** the trace SHALL include rejected or missing fields if clarification is required
