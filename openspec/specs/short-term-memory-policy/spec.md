# short-term-memory-policy Specification

## Purpose
TBD - created by archiving change optimize-context-and-short-term-memory. Update Purpose after archive.
## Requirements
### Requirement: 短时记忆 session 视图
系统 SHALL 提供面向 Agent 的短时记忆 session 视图。短时记忆 SHALL 包含最近消息窗口、会话摘要、pending action 和临时任务状态。

#### Scenario: 构建短时记忆
- **WHEN** Agent 处理带 session_id 的聊天请求
- **THEN** 系统从该 session 构建短时记忆，并将其作为工作记忆 block 提供给 ContextBuilder

#### Scenario: 新会话无历史
- **WHEN** session 中没有历史消息、摘要或 pending action
- **THEN** 短时记忆返回空工作记忆 block 或仅返回当前临时状态，不抛出错误

### Requirement: 最近消息窗口
系统 SHALL 保留当前 session 最近 N 轮原文消息作为短时记忆窗口，并通过 token 预算限制最终注入量。

#### Scenario: 历史低于窗口
- **WHEN** 当前 session 历史消息少于配置窗口
- **THEN** 系统保留全部历史消息作为最近窗口

#### Scenario: 历史超过窗口
- **WHEN** 当前 session 历史消息超过配置窗口
- **THEN** 系统只保留最近窗口内的原文消息，窗口外消息 SHALL 进入摘要候选或不注入

### Requirement: 会话摘要
系统 SHALL 为超出最近窗口的历史提供会话摘要能力。摘要 SHALL 与最近窗口分开存储或计算，并作为可压缩 block 纳入 token 预算。

#### Scenario: 存在旧历史摘要
- **WHEN** session 存在窗口外历史摘要
- **THEN** 系统将摘要作为低于最近窗口优先级的工作记忆 block 注入候选上下文

#### Scenario: 摘要生成失败
- **WHEN** 会话摘要生成或读取失败
- **THEN** 系统记录错误并降级为仅使用最近消息窗口

### Requirement: pending action 注入
系统 SHALL 将当前 session 的 pending action 作为高优先级短时记忆注入，避免用户确认、取消或补充信息时丢失上下文。

#### Scenario: 存在待确认写操作
- **WHEN** session 存在待确认记账、日志、周期或债务操作
- **THEN** 短时记忆包含 pending action 类型、摘要、必要参数和过期时间

#### Scenario: pending action 过期
- **WHEN** pending action 已超过有效期
- **THEN** 系统不再将其注入短时记忆，并清理或标记为 expired

### Requirement: 短时记忆与长期记忆隔离
系统 MUST 将短时记忆与长期记忆区分处理。短时记忆绑定 session，长期记忆绑定用户、farm 或领域事实；Agent 调用方不得把完整长期记忆默认塞入短时记忆窗口。

#### Scenario: 长期记忆命中
- **WHEN** 长期记忆检索返回用户偏好或历史事实
- **THEN** 系统将其作为检索上下文 block，而不是写入最近消息窗口

#### Scenario: session 关闭
- **WHEN** 会话关闭或过期
- **THEN** 该 session 的短时记忆不再作为活跃工作记忆注入，但可用于后续摘要沉淀

