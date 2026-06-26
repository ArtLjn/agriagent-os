## ADDED Requirements

### Requirement: 第 2 期实施范围
系统 SHALL 在第 2 期迁移 `conversation_messages`、`agent_records` 和 `guardrails_logs` 三类对象到 MongoDB，并将 `agent_turns.rule_hits` 限定为评估项。

#### Scenario: 三张表进入实施范围
- **WHEN** 开发者查看第 2 期 MongoDB 迁移配置、Repository 或迁移脚本支持列表
- **THEN** 系统包含 `conversation_messages`、`agent_records` 和 `guardrails_logs`
- **AND** 系统不得将 `agent_turns` 整表或 `agent_turns.rule_hits` 纳入本期写入切换对象

#### Scenario: rule_hits 只输出评估
- **WHEN** 第 2 期实施完成
- **THEN** 系统产出 `agent_turns.rule_hits` 拆分迁移评估结论
- **AND** MySQL `agent_turns.rule_hits` 仍作为运行时读写来源

### Requirement: conversation_messages 文档存储
系统 SHALL 将 `conversation_messages` 行映射到 `conversationMessages` Mongo 集合，并保持会话消息 API 行为兼容。

#### Scenario: 保存单条会话消息
- **WHEN** 服务层保存用户或助手消息
- **THEN** 在 `dual` 模式下系统先写入 MySQL `conversation_messages`
- **AND** 系统将消息以 `mysqlId`、`farmId`、`conversationId`、`sessionId`、`role`、`content`、`contentHash`、`turnId`、`meta` 和 `createdAt` 写入 `conversationMessages`
- **AND** Mongo 写失败不得导致 MySQL 写入回滚

#### Scenario: 批量保存会话消息
- **WHEN** 服务层批量保存同一会话内的多条消息
- **THEN** MySQL 写入仍保持一次事务语义
- **AND** Mongo 二级写入必须按 `mysqlId` 幂等 upsert
- **AND** 任一 Mongo 二级写失败必须创建可重放补偿任务

#### Scenario: 历史消息 API 兼容
- **WHEN** 客户端调用 `/agent/conversations/{session_id}/messages`
- **THEN** 响应中的消息 `id`、`role`、`content`、`skills`、`pending_action`、`pending_plan` 和 `created_at` 与 MySQL 模式保持兼容
- **AND** `mongo-read` 模式下 Mongo 未命中或读取失败时系统回退 MySQL

#### Scenario: 最近消息注入顺序
- **WHEN** 系统读取最近 N 条会话消息用于上下文注入
- **THEN** 返回结果必须按创建时间正序排列
- **AND** 当多条消息时间相同时必须使用 `mysqlId` 保持稳定顺序

### Requirement: agent_records 文档存储
系统 SHALL 将 `agent_records` 行映射到 `agentRecords` Mongo 集合，并保持聊天记录、每日建议缓存和报告历史行为兼容。

#### Scenario: 保存 Agent 输出记录
- **WHEN** 聊天、流式回复、每日建议或报告生成创建 AgentRecord
- **THEN** 在 `dual` 模式下系统先写入 MySQL `agent_records`
- **AND** 系统将记录以 `mysqlId`、`farmId`、`userId`、`conversationId`、`cycleId`、`recordType`、`content`、`meta` 和 `createdAt` 写入 `agentRecords`
- **AND** Mongo 文档中的 `meta` 必须保存为可查询文档或数组，不得只保存为 JSON 字符串

#### Scenario: 每日建议缓存读取
- **WHEN** 系统查找当天最新每日建议缓存
- **THEN** `mongo-read` 模式必须按 `farmId`、`recordType=daily` 和 `createdAt desc` 查询
- **AND** meta 中的 schema version 与 candidate fingerprint 解析结果必须与 MySQL 模式一致

#### Scenario: 报告历史分页
- **WHEN** 客户端查询报告历史或报告分页
- **THEN** 系统返回的 `id`、`cycle_id`、`report_type`、`content`、`structured_data` 和 `created_at` 与 MySQL 模式保持兼容
- **AND** Mongo 读取失败时系统回退 MySQL 并记录回退原因

#### Scenario: 周期关联清理
- **WHEN** 农场或种植周期服务需要清理 AgentRecord 的 `cycle_id` 引用
- **THEN** Repository 必须在当前 storage 模式下保持 MySQL 行为一致
- **AND** 在 `dual` 或 `mongo` 模式下 Mongo 文档中的 `cycleId` 必须同步更新

### Requirement: guardrails_logs 文档存储
系统 SHALL 将 Guardrails 拦截日志映射到 `guardrailsLogs` Mongo 集合，并保持管理员查询与清理行为兼容。

#### Scenario: 创建 Guardrails 日志
- **WHEN** 输入或输出 Guardrails 需要持久化拦截记录
- **THEN** 在 `dual` 模式下系统先写入 MySQL `guardrails_logs`
- **AND** 系统将记录以 `mysqlId`、`farmId`、`triggerType`、`triggerDetail`、`sourceText`、`sourceTextHash` 和 `createdAt` 写入 `guardrailsLogs`
- **AND** 日志和补偿任务不得泄露明文连接串或密钥

#### Scenario: 管理员分页查询
- **WHEN** 管理员调用 `/admin/guardrails-logs`
- **THEN** 系统支持按 `trigger_type` 过滤、分页和按 `created_at desc` 排序
- **AND** 响应结构与 MySQL 模式保持兼容

#### Scenario: 清理旧 Guardrails 日志
- **WHEN** 系统清理指定天数之前的 Guardrails 日志
- **THEN** Repository 必须在 MySQL 和 Mongo 后端执行等价清理
- **AND** 清理失败必须记录包含 code 和上下文的结构化日志

### Requirement: 第 2 期 API 兼容
系统 SHALL 在 MongoDB 第 2 期迁移期间保持现有用户侧、管理员侧和 Data Flywheel API contract 不变。

#### Scenario: 聊天接口不暴露存储细节
- **WHEN** 客户端调用 `/agent/chat` 或 `/agent/chat/stream`
- **THEN** 响应不得新增 MongoDB `_id`
- **AND** 失败语义不得因为 Mongo 二级写失败而改变

#### Scenario: Debug export 保持来源兼容
- **WHEN** 客户端调用 `/agent/conversations/{session_id}/debug-export`
- **THEN** 系统导出的 messages、turns 和 trace 结构必须与 MySQL 模式兼容
- **AND** 若消息从 Mongo 读取，导出中的稳定 ID 仍使用 `mysqlId`

#### Scenario: Data Flywheel 样本来源标记
- **WHEN** Data Flywheel 构造会话样本
- **THEN** 第 2 期实施不得破坏 `chat_record_source` 的兼容语义
- **AND** 若后续改为 Mongo 消息来源，必须通过单独变更更新来源标记和测试
