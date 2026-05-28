## ADDED Requirements

### Requirement: 页面结构
The ledger screen SHALL follow a light financial style with clear hierarchy.

#### Scenario: Ledger layout
- **WHEN** the ledger screen is displayed
- **THEN** it MUST show sections in order: total assets card → monthly income/expense → category tags → transaction records

### Requirement: 收入卡片
Income sections SHALL use green-themed cards.

#### Scenario: Income card appearance
- **WHEN** an income card is rendered
- **THEN** its background MUST be `#EDFDF3`
- **AND** the amount text MUST be `#16A34A`

### Requirement: 支出卡片
Expense sections SHALL use red-themed cards.

#### Scenario: Expense card appearance
- **WHEN** an expense card is rendered
- **THEN** its background MUST be `#FFF1F2`
- **AND** the amount text MUST be `#EF4444`

### Requirement: 浮动按钮
The ledger screen SHALL have a floating action button in the bottom-right corner.

#### Scenario: FAB appearance
- **WHEN** the floating button is rendered
- **THEN** its background MUST use the gradient from `#5B8CFF` to `#8B5CF6` at 135 degrees
