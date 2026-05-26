## ADDED Requirements

### Requirement: 农场上下文摘要组装
系统在调用 Agent 前，SHALL 自动查询数据库组装「农场上下文摘要」，包含当前活跃茬口、近期农事、成本概况、应收应付、未来天气。

#### Scenario: 完整农场状态
- **WHEN** 某农场有 1 个 active 茬口（春季西瓜，伸蔓期）、近期有施肥记录、本月成本 3200 元、有未结清赊账
- **THEN** 组装的摘要包含：活跃茬口信息、最近 3 条农事记录、本月成本汇总、未结清债务列表、未来 3 天天气预报

#### Scenario: 空农场
- **WHEN** 某农场没有 active 茬口、没有近期记录
- **THEN** 摘要只包含天气信息，其他部分显示"暂无"

### Requirement: 摘要注入 Agent Prompt
组装好的上下文摘要 SHALL 作为变量注入到 Agent 的 system prompt 模板中。

#### Scenario: 每日建议生成
- **WHEN** 系统生成每日建议时
- **THEN** `render_prompt("system_base", ...)` 中的 `farm_context_summary` 变量被替换为实际摘要文本

#### Scenario: 用户对话
- **WHEN** 用户向 Agent 提问"我下周该注意什么"
- **THEN** Agent 的 system prompt 中包含农场上下文，Agent 能基于实际茬口状态回答

### Requirement: 摘要长度控制
上下文摘要 SHALL 限制在 500 字以内，避免 token 爆炸。

#### Scenario: 数据量大的农场
- **WHEN** 农场有大量活跃茬口和农事记录
- **THEN** 摘要只保留最近 2 个活跃茬口、最近 3 条农事记录、未结清债务只展示前 3 条
