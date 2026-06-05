## Purpose

定义 context-engineering 能力的行为要求。
## Requirements
### Requirement: ContextBundle 构建
系统 SHALL 通过 Context 工程模块构建 Agent 输入上下文。上下文 SHALL 表示为结构化 `ContextBundle`，包含多个 `ContextBlock`，每个 block 记录来源、用途、优先级、token 估算和过期策略。

#### Scenario: 构建聊天上下文
- **WHEN** Agent 处理聊天请求
- **THEN** Context Builder 返回包含农场状态、当前周期、天气、账务摘要、最近对话和记忆摘要的 ContextBundle

### Requirement: Token 预算控制
Context 工程 SHALL 在注入 Prompt 前执行 token 预算分配。系统 MUST 按安全规则、用户输入、短时上下文、业务上下文、长期记忆和检索结果的优先级决定保留、压缩或丢弃内容。

#### Scenario: 上下文超出预算
- **WHEN** 候选上下文超过配置的 token 预算
- **THEN** 系统保留高优先级 block，压缩或丢弃低优先级 block，并记录预算决策

### Requirement: 上下文选择器
系统 SHALL 为农场状态、种植周期、天气、账务、会话历史、用户设置、短时记忆、长期记忆和检索结果提供独立 selector。Selector SHALL 可独立测试。

#### Scenario: 新增账务上下文
- **WHEN** 开发者调整账务摘要注入逻辑
- **THEN** 修改发生在账务 selector 中，并可通过 selector 单元测试验证

### Requirement: 上下文可观测性
Context Builder SHALL 记录每次请求选中的 block、被压缩的 block、被丢弃的 block、token 估算和耗时。

#### Scenario: 调试上下文缺失
- **WHEN** Agent 回复缺少某项农场信息
- **THEN** 开发者可以通过 trace 查看该信息是否被 selector 选中、是否被预算策略丢弃

### Requirement: 农场上下文包含批次作业和未结人工摘要
系统 SHALL 在农场上下文中注入活跃种植批次、近期作业单和未结人工摘要，用于 Agent 回答和建议生成。

#### Scenario: Agent 回答当前农事状态
- **WHEN** 用户询问“最近西瓜地干了什么”
- **THEN** 系统 SHALL 基于作业单和旧日志合并结果回答近期农事，而不是只读取旧 `farm_logs`

#### Scenario: Agent 回答未付人工
- **WHEN** 用户询问“还欠工人多少钱”
- **THEN** 系统 SHALL 基于未结用工明细或关联账单汇总未付人工

