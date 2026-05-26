## ADDED Requirements

### Requirement: 赊账记录创建
系统 SHALL 支持创建赊账记录，记录类型为 `debt`（我欠别人）或 `receivable`（别人欠我）。每条记录包含对方名称、金额、约定结清日期。

#### Scenario: 向农资店赊购大棚膜
- **WHEN** 用户录入一笔成本，选择类型为"赊账"，填写对方"老张农资店"、金额"3000"、约定还款日"2026-06-30"
- **THEN** 系统创建一条 `record_type=cost`、`record_subtype=debt` 的记录， counterparty="老张农资店"，due_date="2026-06-30"，settled_at 为 NULL

#### Scenario: 买家先拿货后付款
- **WHEN** 用户录入一笔收入，选择类型为"赊账"，填写对方"王老板"、金额"5000"、约定收款日"2026-06-15"
- **THEN** 系统创建一条 `record_type=income`、`record_subtype=receivable` 的记录，counterparty="王老板"，due_date="2026-06-15"

### Requirement: 赊账还款/收款
系统 SHALL 支持对未结清的赊账记录进行还款或收款操作，创建一条关联的结清记录。

#### Scenario: 还农资店欠款
- **WHEN** 用户选择未结清的赊账记录（欠老张农资店 3000 元），点击"还款"，填写实际还款金额"3000"、还款日期"2026-06-25"
- **THEN** 系统创建一条 `record_type=cost`、`record_subtype=direct` 的还款记录，parent_record_id 指向原赊账记录，同时更新原记录的 settled_at="2026-06-25"

#### Scenario: 部分还款
- **WHEN** 用户对 3000 元欠款只还了 2000 元
- **THEN** 系统创建一条 2000 元的还款记录，原赊账记录仍保持未结清状态，剩余待还 1000 元

### Requirement: 赊账列表查询
系统 SHALL 提供赊账列表查询接口，支持按状态（全部/未结清/已结清）、按对方名称筛选。

#### Scenario: 查看未结清赊账
- **WHEN** 用户查询赊账列表，筛选"未结清"
- **THEN** 返回所有 settled_at 为 NULL 的记录，包含原金额、已还金额、剩余待还金额

#### Scenario: 按对方名称筛选
- **WHEN** 用户搜索"老张农资店"
- **THEN** 返回所有 counterparty 包含"老张农资店"的赊账记录

### Requirement: 成本统计排除未结清赊账
系统在统计月度/年度成本时，SHALL 默认只统计 `record_subtype=direct` 的记录，不包含未结清的赊账。

#### Scenario: 月度成本统计
- **WHEN** 系统统计 2026 年 5 月成本
- **THEN** 只包含 5 月创建的现结记录，不包含当月创建的赊账记录（即使其记录日期在 5 月）

### Requirement: 移动端赊账录入入口
移动端记账页面 SHALL 增加"赊账"选项，录入时显示"对方名称"和"约定还款日"字段。

#### Scenario: 记账选择赊账
- **WHEN** 用户在记账页面选择类型为"赊账"
- **THEN** 表单显示"对方名称"和"约定还款日"输入框，保存后同步到后端
