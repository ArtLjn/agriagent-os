## Purpose

定义 agent-platform-architecture 能力的行为要求。
## Requirements
### Requirement: Agent 平台模块边界
系统 SHALL 将成熟 Agent 系统划分为 Agent Runtime、Reflection、Prompt、Context、Memory、Skills、Evaluation、Observability 和业务 modules 边界。Agent Runtime SHALL NOT 直接承担 Prompt 版本治理、上下文选择、长期记忆沉淀、反思策略治理或评测报告职责。

#### Scenario: 架构边界可导航
- **WHEN** 开发者需要修改 Agent 图执行逻辑
- **THEN** 相关代码位于 Agent Runtime 边界内，且不需要修改 Prompt 版本、Memory 存储、Reflection 策略或 Evaluation 报告代码

#### Scenario: 平台能力独立扩展
- **WHEN** 开发者新增长期记忆沉淀能力
- **THEN** 新代码优先进入 Memory 边界，并通过明确接口被 Agent 或 Context 调用

### Requirement: Agent 请求生命周期
系统 SHALL 为每次 Agent 请求定义稳定生命周期：认证与农场上下文、意图规划、上下文构建、Prompt 组合、Runtime 执行、Skill 执行、触发式 Reflection 检查、回复格式化、Memory 观察、Trace 记录和 Evaluation 可回放数据采集。

#### Scenario: 标准聊天请求
- **WHEN** 用户发送 Agent 聊天请求
- **THEN** 系统按标准生命周期处理，并为上下文、Prompt、LLM、Skill、Reflection 和回复阶段生成可追踪事件

### Requirement: API 层保持薄入口
Agent API 路由 SHALL 只负责请求校验、鉴权依赖、调用 application use case 和返回响应。SSE 编排、消息持久化、trace 查询、pending action 组装 SHALL 下沉到 Agent application 或 runtime 边界。

#### Scenario: 修改流式事件编排
- **WHEN** 开发者调整 Agent SSE 事件格式
- **THEN** 修改发生在 Agent application/runtime 边界，而不是 API 路由中

### Requirement: 分阶段迁移兼容性
架构迁移 SHALL 保持现有外部 API 行为兼容。迁移期间允许旧模块 re-export 新模块能力，但每个阶段 MUST 有移除旧入口的后续任务。

#### Scenario: 旧 import 仍可运行
- **WHEN** 迁移 Auth 或 Agent 边界的第一阶段完成
- **THEN** 现有测试和外部 API 仍能通过兼容入口运行

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

