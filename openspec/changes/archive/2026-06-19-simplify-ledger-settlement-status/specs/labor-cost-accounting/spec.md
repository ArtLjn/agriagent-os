## MODIFIED Requirements

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
