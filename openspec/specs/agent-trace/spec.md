## Purpose

定义 agent-trace 能力的行为要求。

## Requirements

### Requirement: 平台级 Trace 事件
Agent Trace SHALL 覆盖 Agent 请求生命周期中的 context_build、prompt_render、llm_call、tool_call、memory_observe、response_format 和 evaluation_capture 事件。

#### Scenario: 完整 Agent 请求追踪
- **WHEN** 用户发送一次触发工具调用的聊天请求
- **THEN** trace 中包含上下文构建、Prompt 渲染、LLM 调用、工具调用和回复格式化事件

### Requirement: Trace 关联 Prompt 和 Context
LLM 调用 trace SHALL 记录 Prompt 版本、ContextBundle 摘要、token 预算使用和被注入的 ContextBlock 类型。

#### Scenario: 调试 Prompt 版本
- **WHEN** 开发者查看某次 LLM 调用 trace
- **THEN** 可以看到该请求使用的 Prompt 版本和上下文摘要

### Requirement: Trace 支持评测回放
Trace SHALL 提供足够信息用于构建评测回放样本，包括用户输入、上下文摘要、Prompt 版本、工具调用、回复摘要和错误信息。

#### Scenario: 从失败请求生成回放用例
- **WHEN** 某次线上请求出现错误工具调用
- **THEN** 开发者可以基于 trace 信息创建评测回放用例
