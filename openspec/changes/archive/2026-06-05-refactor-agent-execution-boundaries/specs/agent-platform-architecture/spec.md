## ADDED Requirements

### Requirement: Agent Application 聊天生命周期所有权
系统 SHALL 由 Agent Application 边界拥有聊天请求生命周期编排，包括会话加载、用户消息保存、pending action 决策、Advisor/Runtime 调用、助手消息保存、Memory observation 和 pending action 响应组装。

#### Scenario: 非流式聊天入口
- **WHEN** API 层收到 `/agent/chat` 请求
- **THEN** API SHALL 调用 Agent Application use case，且聊天生命周期编排 SHALL 不依赖 `services.agent_service` 的独立实现

#### Scenario: 流式聊天入口
- **WHEN** API 层收到 `/agent/chat/stream` 请求
- **THEN** SSE 事件生成 SHALL 由 Agent Application use case 编排，并复用同一 pending action 决策能力

### Requirement: Legacy Agent Service 兼容委托
迁移期间 `services.agent_service` MAY 保留兼容函数，但这些函数 SHALL 委托 Agent Application 或 Agent Executor 的新所有者，不得保留独立聊天编排或 pending action 执行逻辑。

#### Scenario: 旧测试调用兼容函数
- **WHEN** 旧测试或旧模块调用 `chat_with_agent`
- **THEN** 兼容函数 SHALL 委托 Agent Application 的聊天实现，并保持外部行为兼容

### Requirement: Runtime 消费预构建平台输入
Agent Runtime SHALL 优先消费由 Application 或端口准备好的 prompt、context、memory 和 tool policy 输入。Runtime SHALL NOT 直接拥有 Prompt 版本治理、Context selector 实现、Memory 存储实现或 pending action 确认执行逻辑。

#### Scenario: Runtime 执行 LLM 节点
- **WHEN** Runtime LLM 节点需要 system prompt 和 runtime context
- **THEN** 节点 SHALL 使用预构建输入或窄端口获取结果，而不是直接组合平台治理细节

### Requirement: 架构传感器覆盖 Agent 边界
系统 SHALL 提供自动化检查，阻止新增代码绕过 Agent Application、Agent Executor 和 Runtime 边界所有权。

#### Scenario: 新增重复 pending action 执行
- **WHEN** 开发者在 `services.agent_service` 或 `agent.advisor` 中新增直接执行 pending action 的代码
- **THEN** 架构检查 SHALL 失败并提示使用 Agent Executor 的单一入口
