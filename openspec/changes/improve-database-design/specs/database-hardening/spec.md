## ADDED Requirements

### Requirement: 关键关系外键完整性
系统 SHALL 为用户、农场、设置、反馈、账务分类和 Agent 记录等关键跨表关系配置数据库外键约束，并按业务语义配置删除策略。

#### Scenario: 阻止悬挂农场数据
- **WHEN** 新增或更新依赖 `farm_id` 的业务记录
- **THEN** 数据库必须拒绝引用不存在的 `farms.id`

#### Scenario: 保留反馈记录
- **WHEN** 被评价的会话消息被删除
- **THEN** `feedback_records.conversation_message_id` 必须被置空且反馈记录保留

### Requirement: 账务分类引用完整性
系统 SHALL 使用 `cost_records.category_id` 引用 `cost_categories.id`，并保留历史分类名称快照用于展示。

#### Scenario: 创建账务记录
- **WHEN** 用户创建收入或支出记录并选择分类
- **THEN** 系统必须保存 `category_id` 并写入 `category_name_snapshot`

#### Scenario: 分类改名后展示历史账务
- **WHEN** 成本分类名称被修改
- **THEN** 历史账务记录必须仍可展示创建时的分类名称快照

### Requirement: 冗余索引治理
系统 SHALL 移除主键列上的冗余二级索引，并保留业务查询需要的索引。

#### Scenario: 主键索引审查
- **WHEN** 迁移脚本检查表结构
- **THEN** 对已经作为 PRIMARY KEY 的 `id` 列不得保留单独的 `ix_*_id` 二级索引

### Requirement: 迁移前数据完整性检查
系统 SHALL 在添加新外键或收紧约束前检查历史数据，并输出无法迁移的数据清单。

#### Scenario: 检测悬挂外键
- **WHEN** 运行迁移前检查
- **THEN** 系统必须列出引用不存在用户、农场、会话、分类或作物周期的记录

#### Scenario: 检测无法匹配的账务分类
- **WHEN** 运行账务分类回填检查
- **THEN** 系统必须列出无法按农场、分类名和收支类型匹配到 `cost_categories` 的 `cost_records`
