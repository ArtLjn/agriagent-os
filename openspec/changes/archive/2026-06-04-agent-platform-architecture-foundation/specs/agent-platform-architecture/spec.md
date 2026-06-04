## ADDED Requirements

### Requirement: Agent 平台模块边界
系统 SHALL 将成熟 Agent 系统划分为 Agent Runtime、Prompt、Context、Memory、Skills、Evaluation、Observability 和业务 modules 边界。Agent Runtime SHALL NOT 直接承担 Prompt 版本治理、上下文选择、长期记忆沉淀或评测报告职责。

#### Scenario: 架构边界可导航
- **WHEN** 开发者需要修改 Agent 图执行逻辑
- **THEN** 相关代码位于 Agent Runtime 边界内，且不需要修改 Prompt 版本、Memory 存储或 Evaluation 报告代码

#### Scenario: 平台能力独立扩展
- **WHEN** 开发者新增长期记忆沉淀能力
- **THEN** 新代码优先进入 Memory 边界，并通过明确接口被 Agent 或 Context 调用

### Requirement: Agent 请求生命周期
系统 SHALL 为每次 Agent 请求定义稳定生命周期：认证与农场上下文、意图规划、上下文构建、Prompt 组合、Runtime 执行、Skill 执行、回复格式化、Memory 观察、Trace 记录和 Evaluation 可回放数据采集。

#### Scenario: 标准聊天请求
- **WHEN** 用户发送 Agent 聊天请求
- **THEN** 系统按标准生命周期处理，并为上下文、Prompt、LLM、Skill 和回复阶段生成可追踪事件

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
