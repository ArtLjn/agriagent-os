# labor-cost-accounting Specification

## Purpose
TBD - created by archiving change stabilize-labor-cost-accounting. Update Purpose after archive.
## Requirements
### Requirement: 全局工人档案
The system SHALL manage workers as farm-level resources that can participate in multiple crop cycles.

#### Scenario: Worker reused across cycles
- **WHEN** a worker is selected for labor in a watermelon cycle and later selected for a bean cycle
- **THEN** the system MUST use the same worker profile
- **AND** the worker detail MUST show labor history grouped by cycle

#### Scenario: Create worker during wage entry
- **WHEN** a user enters a worker name that does not exist while recording wages
- **THEN** the system MUST create a lightweight worker profile for the current farm
- **AND** the wage record MUST reference the newly created worker

### Requirement: 结构化记工资
The system SHALL require wage records to bind to a crop cycle and use structured selectors for business context.

#### Scenario: Wage entry with dropdown context
- **WHEN** the user opens the wage entry page from the home worker shortcut
- **THEN** the page MUST provide selectors for crop cycle, crop arrangement or crop name, operation type, worker, wage date, pay type, quantity, unit price, paid amount, and note

#### Scenario: Wage entry from cycle context
- **WHEN** the user opens wage entry from a cycle detail page
- **THEN** the cycle selector MUST default to that cycle
- **AND** the user MUST be able to change the worker and operation type without re-entering cycle details

### Requirement: 人工成本账单唯一生成
The system SHALL create or update exactly one labor cost record for each wage source and keep its settlement status aligned with the wage payment state.

#### Scenario: Save wage creates labor cost
- **WHEN** a wage record with payable amount is saved
- **THEN** the system MUST create a cost record with record type expense and labor category
- **AND** the cost record MUST include source_type and source_id linking back to the wage source
- **AND** the cost record amount MUST equal the wage payable amount
- **AND** the cost record settled amount MUST equal the wage paid amount
- **AND** the cost record settlement status MUST reflect whether the wage is unpaid, partially paid, or settled

#### Scenario: Duplicate save does not duplicate expense
- **WHEN** the same wage save request is retried or submitted twice
- **THEN** the system MUST update the existing source-linked labor cost record
- **AND** the total expense MUST NOT increase twice

#### Scenario: Wage update synchronizes cost
- **WHEN** an existing wage record changes quantity, unit price, paid amount, or settlement status
- **THEN** the linked labor cost record MUST be recalculated from the latest wage data
- **AND** the linked labor cost record settled amount and settlement status MUST match the latest wage payment state

### Requirement: 工人欠款统计
The system SHALL calculate payable, paid, and unpaid labor amounts from labor entries and linked cost records.

#### Scenario: Worker unpaid summary
- **WHEN** the worker management page is opened
- **THEN** each worker MUST show total payable, total paid, and total unpaid amounts across all active cycles

#### Scenario: Cycle labor summary
- **WHEN** a cycle detail page is opened
- **THEN** it MUST show labor cost and unpaid labor summary only for that cycle
- **AND** it MUST NOT imply that the worker belongs exclusively to that cycle

### Requirement: 利润总支出一致性
The system SHALL calculate profit total expense from the same cost records used by the ledger page.

#### Scenario: Profit expense matches ledger
- **WHEN** profit is queried for a crop cycle
- **THEN** total expense MUST equal the sum of non-deleted expense cost records for the same farm and cycle
- **AND** labor cost records generated from wages MUST be included exactly once

#### Scenario: Ledger filter from profit
- **WHEN** the user taps a labor expense amount in profit or cycle labor summary
- **THEN** the ledger page MUST open with filters for the same cycle and labor category or labor source
- **AND** the displayed ledger total MUST match the tapped amount

