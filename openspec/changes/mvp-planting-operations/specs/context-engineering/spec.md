## ADDED Requirements

### Requirement: 农场上下文包含批次作业和未结人工摘要
系统 SHALL 在农场上下文中注入活跃种植批次、近期作业单和未结人工摘要，用于 Agent 回答和建议生成。

#### Scenario: Agent 回答当前农事状态
- **WHEN** 用户询问“最近西瓜地干了什么”
- **THEN** 系统 SHALL 基于作业单和旧日志合并结果回答近期农事，而不是只读取旧 `farm_logs`

#### Scenario: Agent 回答未付人工
- **WHEN** 用户询问“还欠工人多少钱”
- **THEN** 系统 SHALL 基于未结用工明细或关联账单汇总未付人工
