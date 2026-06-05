## Purpose

定义 ledger-ui-redesign 能力的行为要求。
## Requirements
### Requirement: 页面结构
The ledger screen SHALL follow a light financial style with clear hierarchy and source-aware records.

#### Scenario: Ledger layout
- **WHEN** the ledger screen is displayed
- **THEN** it MUST show sections in order: total assets card → monthly income/expense → category and source filters → transaction records
- **AND** labor records generated from wages or operation work orders MUST expose their source in the transaction records section

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

### Requirement: 账单列表识别作业单人工成本
系统 SHALL 在账单列表和成本详情中标识由农事作业单生成或关联的人工成本。

#### Scenario: 查看来自作业单的人工费
- **WHEN** 用户查看一条由“人工授粉”作业单产生的人工成本
- **THEN** 系统 SHALL 展示其来源作业类型和关联批次，并避免提示用户重复录入同一笔人工费

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

