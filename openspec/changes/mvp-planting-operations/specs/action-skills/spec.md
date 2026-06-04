## ADDED Requirements

### Requirement: Agent 可以创建农事作业单和用工记录
系统 SHALL 提供写操作 Skill，使 Agent 能在用户确认后创建农事作业单，并可同时记录工人用工和人工成本。

#### Scenario: 自然语言记录授粉用工
- **WHEN** 用户说“今天东大棚 4 个工人给西瓜授粉，每人 200，先付老王 200”
- **THEN** Agent SHALL 生成待确认动作，包含作业类型、作用范围、工人明细、应付金额、已付金额和关联批次

#### Scenario: 用户确认后写入
- **WHEN** 用户确认创建作业单
- **THEN** 系统 SHALL 写入作业单、用工明细和人工成本关联记录
