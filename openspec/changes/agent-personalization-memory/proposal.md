## Why

现有个性化页面使用演示数据，长期记忆读取为空。需要按已确认计划将用户配置与记忆管理接入持久化和 Agent 上下文。

## What Changes

- 实现个人配置的真实读写与版本冲突保护。
- 实现带身份范围的明确记忆管理与上下文注入。
- 移除真实接口失败时假装保存成功的演示回退。
- 一次交付明确记忆工具、临时对话、自动学习、移动端设置和语义检索。

## Capabilities

### New Capabilities

- `agent-personalization`: 用户配置、记忆管理和上下文生效契约。

### Modified Capabilities

无。

## Impact

涉及 Agent API、Memory Service、Mongo adapter、ContextBuilder、Web 与移动端 API、页面和测试。不修改公共知识集合，不新增运行依赖。
