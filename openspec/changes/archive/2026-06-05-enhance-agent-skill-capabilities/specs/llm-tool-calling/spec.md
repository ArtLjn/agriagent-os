## MODIFIED Requirements

### Requirement: Tool Executor 独立边界
系统 SHALL 通过 Tool Executor 执行 Skill 调用。Tool Executor SHALL 基于 Skill metadata 负责权限检查、参数校验、并行执行、错误包装、写操作确认、缓存失效和 trace 事件记录。

#### Scenario: 多工具调用
- **WHEN** LLM 返回多个 tool_calls
- **THEN** Tool Executor 统一调度执行，并为每个工具调用记录结果和错误

#### Scenario: Metadata 驱动写操作拦截
- **WHEN** LLM 选择 metadata.permission_level 为 `write_confirm` 的 Skill
- **THEN** Tool Executor 根据 metadata 进入 pending action 确认流程，而不是依赖硬编码 Skill 名单

### Requirement: Skill 权限分级
每个 Skill SHALL 声明权限等级，至少区分只读、需要确认的写操作、管理员操作和外部网络访问。Tool Executor MUST 根据权限等级决定是否允许执行、是否需要确认、是否需要管理员身份和是否需要网络访问许可。

#### Scenario: 写操作需要确认
- **WHEN** LLM 选择创建成本记录的 Skill
- **THEN** Tool Executor 根据权限等级进入 pending action 确认流程，而不是直接写入

#### Scenario: 管理员 Skill 需要管理员身份
- **WHEN** LLM 选择 metadata.permission_level 为 `admin` 的 Skill
- **THEN** Tool Executor verifies the current user has administrator permission before executing the Skill

### Requirement: Tool 参数标准化
Tool Executor SHALL 在执行前对参数进行 schema 校验，并在失败时返回结构化错误，不得将未校验参数传给业务写操作。参数错误 SHALL 记录 trace，并可被 Evaluation 识别为参数质量失败。

#### Scenario: 参数缺失
- **WHEN** LLM 调用写操作 Skill 但缺少必填金额
- **THEN** Tool Executor 返回参数错误，并阻止业务写入

#### Scenario: 参数错误进入评测报告
- **WHEN** Tool Executor rejects a tool call because `start_date` is invalid
- **THEN** trace records the validation error and Evaluation can classify the case as `parameter_error`
