## ADDED Requirements

### Requirement: Tool Executor 独立边界
系统 SHALL 通过 Tool Executor 执行 Skill 调用。Tool Executor SHALL 负责权限检查、参数校验、并行执行、错误包装、写操作确认和 trace 事件记录。

#### Scenario: 多工具调用
- **WHEN** LLM 返回多个 tool_calls
- **THEN** Tool Executor 统一调度执行，并为每个工具调用记录结果和错误

### Requirement: Skill 权限分级
每个 Skill SHALL 声明权限等级，至少区分只读、需要确认的写操作、管理员操作和外部网络访问。

#### Scenario: 写操作需要确认
- **WHEN** LLM 选择创建成本记录的 Skill
- **THEN** Tool Executor 根据权限等级进入 pending action 确认流程，而不是直接写入

### Requirement: Tool 参数标准化
Tool Executor SHALL 在执行前对参数进行 schema 校验，并在失败时返回结构化错误，不得将未校验参数传给业务写操作。

#### Scenario: 参数缺失
- **WHEN** LLM 调用写操作 Skill 但缺少必填金额
- **THEN** Tool Executor 返回参数错误，并阻止业务写入
