## MODIFIED Requirements

### Requirement: 短时记忆 session 视图
系统 SHALL 提供面向 Agent 的短时记忆 session 视图。短时记忆 SHALL 包含最近完整 Turn 原文窗口、会话摘要、当前 pending action、临时任务状态、snapshot revision 和 source status；工具原始 payload 不得默认进入该视图。

#### Scenario: 构建短时记忆
- **WHEN** Agent 处理带 `conversation_id` 的聊天请求
- **THEN** 系统从版本化 Conversation snapshot 构建短时记忆，并将其作为工作记忆 Block 提供给 ContextBuilder

#### Scenario: 新会话无历史
- **WHEN** session 中没有历史消息、摘要或 pending action
- **THEN** 短时记忆返回空工作记忆 Block 或仅返回当前临时状态，不抛出错误

### Requirement: 最近消息窗口
系统 SHALL 保留当前 session 最近配置数量的完整 Turn 原文消息，并通过 token 预算限制最终注入量；窗口外消息 SHALL 进入会话摘要候选，而不能只按单条 message 截断。

#### Scenario: 历史低于窗口
- **WHEN** 当前 session 历史少于配置窗口
- **THEN** 系统保留全部完整 Turn 作为最近窗口

#### Scenario: 历史超过窗口
- **WHEN** 当前 session 历史超过配置窗口或 token budget
- **THEN** 系统保留最近完整 Turn，窗口外历史进入摘要候选，并记录裁剪边界和原因

### Requirement: 会话摘要
系统 SHALL 为超出最近窗口的历史提供会话摘要能力。摘要 SHALL 与消息窗口独立存储或计算，包含来源消息范围、摘要 revision、状态和内容 hash，并作为可压缩 Block 纳入 token 预算。

#### Scenario: 存在旧历史摘要
- **WHEN** session 存在窗口外历史摘要
- **THEN** 系统将摘要作为低于最近原文窗口优先级的工作记忆 Block 注入候选上下文

#### Scenario: 摘要生成失败
- **WHEN** 会话摘要生成或读取失败
- **THEN** 系统记录错误并降级为最近完整 Turn 窗口，不生成伪造摘要

### Requirement: pending action 注入
系统 SHALL 将当前 session 的 pending action 作为高优先级短时记忆注入，避免用户确认、取消或补充信息时丢失上下文；pending action MUST 带过期时间和状态。

#### Scenario: 存在待确认写操作
- **WHEN** session 存在待确认记账、日志、周期或债务操作
- **THEN** 短时记忆包含 pending action 类型、摘要、必要参数、来源 Turn 和过期时间

#### Scenario: pending action 过期
- **WHEN** pending action 已超过有效期
- **THEN** 系统不再将其注入短时记忆，并清理或标记为 expired

## ADDED Requirements

### Requirement: Summary compare and swap
摘要写入 MUST 使用 source conversation revision 或等价的 compare-and-swap 条件，且同一会话同一来源范围的摘要写入必须幂等。

#### Scenario: Concurrent summary generation
- **WHEN** 两个 Worker 基于同一历史生成相同摘要
- **THEN** 只有一个版本被接受，另一个写入返回幂等成功或 conflict，不得覆盖更新的会话消息

### Requirement: Short-term memory source status
短时记忆视图 SHALL 明确标记 `mongo`、`redis_snapshot`、`empty` 或 `unavailable` 来源。

#### Scenario: Mongo unavailable
- **WHEN** Mongo snapshot 暂时不可读
- **THEN** Agent 返回 `unavailable` source status，由 application 明确决定继续当前 Turn 或终止，不读取本地文件伪造历史
