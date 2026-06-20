## MODIFIED Requirements

### Requirement: 页面结构
The ledger screen SHALL follow a light financial style with clear hierarchy, source-aware records, and settlement-aware totals.

#### Scenario: Ledger layout
- **WHEN** the ledger screen is displayed
- **THEN** it MUST show sections in order: settlement summary card → monthly occurred income/expense → category, settlement status, and source filters → transaction records
- **AND** labor records generated from wages or operation work orders MUST expose their source in the transaction records section
- **AND** unsettled debt or receivable records MUST expose whether they are unpaid, unreceived, partial, or settled

## ADDED Requirements

### Requirement: 账单总览展示结算口径
The ledger screen SHALL display occurred, settled, and unsettled amounts without implying unsettled debt has already been paid or received.

#### Scenario: Ledger summary with debt
- **WHEN** the current month contains settled expenses and unsettled debt expenses
- **THEN** the ledger summary MUST show monthly occurred expense separately from paid expense
- **AND** the ledger summary MUST show current unpaid amount

#### Scenario: Ledger summary with receivable
- **WHEN** the current month contains settled income and unsettled receivable income
- **THEN** the ledger summary MUST show monthly occurred income separately from received income
- **AND** the ledger summary MUST show current unreceived amount

### Requirement: 账单列表展示结算状态
The ledger screen SHALL show settlement state on each debt, receivable, labor, or partially settled record.

#### Scenario: Unsettled expense label
- **WHEN** an expense record has `settlement_status="unsettled"`
- **THEN** the transaction record MUST display an unpaid label and remaining amount
- **AND** the amount display MUST NOT make the record look like a completed cash payment

#### Scenario: Partially settled label
- **WHEN** a record has `settlement_status="partial"`
- **THEN** the transaction record MUST display settled amount and remaining amount
- **AND** the record detail MUST allow the user to understand how much is still unpaid or unreceived
