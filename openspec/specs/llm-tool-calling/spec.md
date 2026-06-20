## Purpose

定义 llm-tool-calling 能力的行为要求。
## Requirements
### Requirement: Tool Executor 独立边界
系统 SHALL 通过 Tool Executor 执行 Skill 调用。Tool Executor SHALL 基于 Skill metadata 负责权限检查、参数校验、并行执行、错误包装、写操作确认、缓存失效和 trace 事件记录。

#### Scenario: 多工具调用
- **WHEN** LLM 返回多个 tool_calls
- **THEN** Tool Executor 统一调度执行，并为每个工具调用记录结果和错误

#### Scenario: Metadata 驱动写操作拦截
- **WHEN** LLM 选择 metadata.permission_level 为 `write_confirm` 的 Skill
- **THEN** Tool Executor 根据 metadata 进入 pending action 确认流程，而不是依赖硬编码 Skill 名单

### Requirement: Skill 权限分级
每个 Skill SHALL 声明权限等级，至少区分只读、需要确认的写操作、管理员操作和外部网络访问。Tool Executor MUST 根据 metadata.permission_level 决定是否允许执行、是否需要确认、是否需要管理员身份、是否需要外部网络许可；硬编码写操作名单只能作为 legacy fallback，不得覆盖显式 metadata。

#### Scenario: 写操作需要确认
- **WHEN** LLM 选择创建成本记录的 Skill
- **THEN** Tool Executor 根据权限等级进入 pending action 确认流程，而不是直接写入

#### Scenario: 管理员 Skill 需要管理员身份
- **WHEN** LLM 选择 metadata.permission_level 为 `admin` 的 Skill
- **THEN** Tool Executor verifies the current user has administrator permission before executing the Skill

#### Scenario: 外部网络 Skill 需要启用许可
- **WHEN** LLM 选择 metadata.permission_level 为 `external_network` 的 Skill
- **THEN** Tool Executor SHALL verify that external network Skills are enabled by configuration before execution
- **AND** if disabled, Tool Executor SHALL return a user-safe failure message and record a trace with status `disabled`

#### Scenario: 显式只读 metadata 覆盖 legacy 写名单
- **WHEN** a Skill name appears in a legacy write list
- **AND** its explicit metadata declares `permission_level=read`
- **THEN** Tool Executor SHALL treat it as read-only and execute without creating a pending action

### Requirement: Metadata completeness gate for write and admin Skills
The system SHALL require complete metadata for every write, admin, and external network Skill before it is considered enabled.

#### Scenario: Write Skill incomplete metadata
- **WHEN** a write Skill has `metadata_incomplete=true`
- **THEN** the coverage audit SHALL report the Skill as not production-ready
- **AND** the Skill SHALL require an implementation task to declare full confirmation schema and cache invalidation

### Requirement: Disabled Skill execution behavior
Disabled Skills SHALL be excluded from tool selection and rejected if directly requested by a model tool call.

#### Scenario: Disabled web search requested
- **WHEN** `web_search` is disabled by configuration
- **AND** LLM returns a `web_search` tool call
- **THEN** Tool Executor SHALL reject the call without external network access
- **AND** trace SHALL include the disabled reason

### Requirement: Tool 参数标准化
Tool Executor SHALL 在执行前对参数进行 schema 校验，并在失败时返回结构化错误，不得将未校验参数传给业务写操作。参数错误 SHALL 记录 trace，并可被 Evaluation 识别为参数质量失败。

#### Scenario: 参数缺失
- **WHEN** LLM 调用写操作 Skill 但缺少必填金额
- **THEN** Tool Executor 返回参数错误，并阻止业务写入

#### Scenario: 参数错误进入评测报告
- **WHEN** Tool Executor rejects a tool call because `start_date` is invalid
- **THEN** trace records the validation error and Evaluation can classify the case as `parameter_error`

### Requirement: Pending Action Execution 单一入口
系统 SHALL 通过 Agent Executor 边界内的单一 pending action 执行入口处理写操作确认、取消、修改和链式后续动作。非流式聊天、流式聊天和 Advisor 兼容入口 MUST NOT 各自实现独立的 pending action 执行逻辑。

#### Scenario: 记账确认统一执行
- **WHEN** 用户先请求记录一笔支出并在下一轮回复“确认”
- **THEN** 非流式聊天和流式聊天 SHALL 调用同一个 pending action 执行入口来执行 `create_cost_record`

#### Scenario: Advisor 兼容入口委托执行
- **WHEN** Advisor 兼容入口检测到用户确认已有 pending action
- **THEN** Advisor SHALL 委托 Agent Executor 的 pending action 执行入口，而不是直接调用 SkillManager 或 LangChain Tool 执行写操作

### Requirement: 写操作执行后缓存失效一致
系统 SHALL 在确认执行写操作 Skill 后，按 Skill 的缓存失效映射清理相关只读 Skill 缓存，并在所有调用路径保持一致。

#### Scenario: 记账后账务缓存失效
- **WHEN** `create_cost_record` pending action 被确认执行成功
- **THEN** 系统 SHALL 清理账务汇总、账务分析和农场状态相关缓存

### Requirement: Pending Action Trace 一致性
系统 SHALL 为 pending action 的拦截、确认执行、取消和失败记录一致的 trace 事件，事件中至少包含 skill 名称、输入参数、执行状态和错误信息。

#### Scenario: 写操作被拦截为待确认
- **WHEN** LLM 返回 `create_cost_record` tool call
- **THEN** 系统 SHALL 记录该 tool call 被拦截为 pending action 的 trace 事件

#### Scenario: 确认执行失败
- **WHEN** pending action 确认执行时 Skill 抛出异常
- **THEN** 系统 SHALL 记录失败 trace，并返回用户可理解的失败回复

