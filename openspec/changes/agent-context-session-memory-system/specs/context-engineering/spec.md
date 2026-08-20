## MODIFIED Requirements

### Requirement: ContextBundle 构建
系统 SHALL 通过 Context 工程模块构建 Agent 输入上下文。上下文 SHALL 表示为结构化 `ContextBundle`，包含 `system_contract`、`tool_schema`、`task_input`、`hot_context`、`pending_action`、`session_summary`、`recent_turns`、`memory_hits` 和动态观察等 ContextBlock；每个 Block 记录来源、用途、优先级、required、可压缩性、token 估算、版本和过期策略。

#### Scenario: 构建聊天上下文
- **WHEN** Agent 处理聊天请求
- **THEN** Context Builder 返回可按优先级裁剪的 ContextBundle，并包含会话 revision、summary revision、工具 Schema 版本和预算结果

#### Scenario: 当前 Turn 观察进入 Context
- **WHEN** 当前 Turn 完成工具调用并获得 observation
- **THEN** 下一次 LLM 调用的 ContextBundle SHALL 包含该 observation 或其受控摘要，且不需要重新读取完整历史 Tool payload

### Requirement: Token 预算控制
Context 工程 SHALL 在注入 Prompt 前执行 token 预算分配。系统 MUST 按安全规则、用户输入、短时上下文、业务上下文、长期记忆和检索结果的优先级决定保留、压缩或丢弃内容，并预留模型输出空间。

#### Scenario: 上下文超出预算
- **WHEN** 候选上下文、Tool Schema 和工具结果总量超过 usable budget
- **THEN** 系统保留高优先级 Block，压缩或丢弃低优先级 Block，并记录 budget decision、drop reason 和 response reserve

#### Scenario: 无法可靠估算 token
- **WHEN** 当前模型 tokenizer 不可用或网关未返回真实 usage
- **THEN** 系统 SHALL 使用配置的保守估算器，并在 Context trace 中标记 `estimation_mode=approximate`

### Requirement: 上下文选择器
系统 SHALL 为农场状态、种植周期、种植单元、作业单、工人、人工未结摘要、天气、账务、会话历史、用户设置、短时记忆、长期记忆和检索结果提供独立 selector。Selector SHALL 可独立测试，并可由 Skill metadata 的 context dependencies 触发；selector 输出必须形成有来源和预算属性的 ContextBlock。

#### Scenario: 新增账务上下文
- **WHEN** 开发者调整账务摘要注入逻辑
- **THEN** 修改发生在账务 selector 中，并可通过 selector 单元测试验证

#### Scenario: 更新茬口需要活跃批次上下文
- **WHEN** Tool selection includes `update_crop_cycle`
- **THEN** ContextPolicy selects crop cycle context and includes candidate active or planned cycles needed for target resolution

#### Scenario: 结算人工需要工人和未付摘要
- **WHEN** Tool selection includes `settle_labor_payment`
- **THEN** ContextPolicy selects worker context and unpaid labor summary context

### Requirement: 上下文可观测性
Context Builder SHALL 记录每次请求选中的 block、被压缩的 block、被丢弃的 block、token 估算、耗时和触发该 block 的 Skill metadata dependency，并记录 Context source status 和 snapshot revision。

#### Scenario: 调试上下文缺失
- **WHEN** Agent 回复缺少某项农场信息
- **THEN** 开发者可以通过 trace 查看该信息是否被 selector 选中、是否被预算策略丢弃、是否来自 fallback 或是否读取失败

#### Scenario: 查看 Skill 触发的上下文
- **WHEN** 开发者查看一次 `update_crop_cycle` 请求 trace
- **THEN** trace shows which context blocks were selected because of `update_crop_cycle` context dependencies
