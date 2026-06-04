## ADDED Requirements

### Requirement: 人工成本来源展示
The ledger screen SHALL display source information for labor cost records created from wage or operation workflows.

#### Scenario: Labor source label
- **WHEN** a labor cost record generated from wage entry or an operation work order is shown in the ledger
- **THEN** the record MUST display a source label such as "来自工资记录" or "来自农事作业"
- **AND** tapping the label or record MUST allow the user to navigate to the related wage, worker, or operation context when available

### Requirement: 账单筛选支持人工来源
The ledger screen SHALL support filters for cycle, labor category, and source type so related pages can deep-link into matching records.

#### Scenario: Open ledger from worker or profit page
- **WHEN** the ledger page is opened with cycle and labor filters
- **THEN** it MUST show only matching labor cost records
- **AND** the visible expense total MUST equal the filtered records sum

## MODIFIED Requirements

### Requirement: 页面结构
The ledger screen SHALL follow a light financial style with clear hierarchy and source-aware records.

#### Scenario: Ledger layout
- **WHEN** the ledger screen is displayed
- **THEN** it MUST show sections in order: total assets card → monthly income/expense → category and source filters → transaction records
- **AND** labor records generated from wages or operation work orders MUST expose their source in the transaction records section
