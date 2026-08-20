## MODIFIED Requirements

### Requirement: 平台级 Trace 事件
Agent Trace SHALL 覆盖 Agent 请求生命周期中的 admission、context_build、prompt_render、skill_router、llm_call、tool_call、memory_read、memory_observe、summary_compaction、response_format 和 evaluation_capture 事件；事件必须可关联 conversation、turn、trace 和 source status。

#### Scenario: 完整 Agent 请求追踪
- **WHEN** 用户发送一次触发工具调用的聊天请求
- **THEN** trace 中包含上下文构建、工具候选、LLM 调用、工具调用、记忆观察和回复格式化事件，且能按 parent span 还原执行顺序

### Requirement: Trace 关联 Prompt 和 Context
LLM 调用 trace SHALL 记录 Prompt 版本、ContextBundle 摘要、conversation/summary/memory revision、token 预算使用、Tool Schema 模式、被注入的 ContextBlock 类型及其保留/压缩/丢弃结果。

#### Scenario: 调试 Prompt 版本
- **WHEN** 开发者查看某次 LLM 调用 trace
- **THEN** 可以看到该请求使用的 Prompt 版本、Context source、摘要版本、预算结果和上下文摘要

### Requirement: Trace 支持评测回放
Trace SHALL 提供足够信息用于构建评测回放样本，包括用户输入摘要、ContextBlock 摘要、Prompt 版本、工具候选与调用、回复摘要、revision、预算决策和错误信息。

#### Scenario: 从失败请求生成回放用例
- **WHEN** 某次线上请求出现错误工具调用或上下文缺失
- **THEN** 开发者可以基于 trace 信息创建评测回放用例，并区分模型未选择、工具未执行、Context 未注入和持久化失败

## ADDED Requirements

### Requirement: Context source divergence warning
Trace SHALL 在 Mongo、Redis snapshot、summary revision 或 Memory source 不一致时记录结构化 warning，不得把缺失证据解释为业务不存在。

#### Scenario: Conversation source divergence
- **WHEN** Conversation state、消息投影或 Redis Turn 对同一 conversation 返回不同 revision 或状态
- **THEN** trace 记录 `context_source_divergence`，包含各 source status、revision 和差异摘要

### Requirement: Budget decision observability
Trace summary SHALL 聚合 Context token 使用、response reserve、Tool Schema token、压缩次数、丢弃 Block 数、summary 生成次数和 context budget error。

#### Scenario: Context budget exceeded
- **WHEN** required Block 加上输出预留后超过模型容量
- **THEN** Turn 和 Trace summary 都记录结构化 budget error，且不得只留下一个泛化的 LLM failure
