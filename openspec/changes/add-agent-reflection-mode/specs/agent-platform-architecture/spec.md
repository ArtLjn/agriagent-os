## MODIFIED Requirements

### Requirement: Agent 请求生命周期
系统 SHALL 为每次 Agent 请求定义稳定生命周期：认证与农场上下文、意图规划、上下文构建、Prompt 组合、Runtime 执行、Skill 执行、触发式 Reflection 检查、回复格式化、Memory 观察、Trace 记录和 Evaluation 可回放数据采集。

#### Scenario: 标准聊天请求
- **WHEN** 用户发送 Agent 聊天请求
- **THEN** 系统按标准生命周期处理，并为上下文、Prompt、LLM、Skill、Reflection 和回复阶段生成可追踪事件

### Requirement: Agent 平台模块边界
系统 SHALL 将成熟 Agent 系统划分为 Agent Runtime、Reflection、Prompt、Context、Memory、Skills、Evaluation、Observability 和业务 modules 边界。Agent Runtime SHALL NOT 直接承担 Prompt 版本治理、上下文选择、长期记忆沉淀、反思策略治理或评测报告职责。

#### Scenario: 架构边界可导航
- **WHEN** 开发者需要修改 Agent 图执行逻辑
- **THEN** 相关代码位于 Agent Runtime 边界内，且不需要修改 Prompt 版本、Memory 存储、Reflection 策略或 Evaluation 报告代码

#### Scenario: 平台能力独立扩展
- **WHEN** 开发者新增长期记忆沉淀能力
- **THEN** 新代码优先进入 Memory 边界，并通过明确接口被 Agent 或 Context 调用
