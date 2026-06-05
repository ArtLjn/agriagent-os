## ADDED Requirements

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
