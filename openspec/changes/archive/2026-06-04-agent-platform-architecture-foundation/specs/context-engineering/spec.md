## ADDED Requirements

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
