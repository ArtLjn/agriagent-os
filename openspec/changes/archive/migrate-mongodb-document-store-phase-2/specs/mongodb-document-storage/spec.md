## ADDED Requirements

### Requirement: 第 2 期 Mongo 集合与索引初始化
系统 SHALL 为第 2 期迁移对象创建 MongoDB 集合与索引，覆盖 `conversationMessages`、`agentRecords` 和 `guardrailsLogs`。

#### Scenario: 初始化第 2 期集合索引
- **WHEN** 开发者运行 MongoDB 索引初始化脚本
- **THEN** 系统为 `conversationMessages`、`agentRecords` 和 `guardrailsLogs` 创建 `{ mysqlId: 1 }` 唯一索引
- **AND** 系统为每个集合创建以 `farmId` 为前缀的业务查询索引
- **AND** 脚本重复运行必须幂等

#### Scenario: conversationMessages 索引
- **WHEN** 初始化 `conversationMessages` 集合
- **THEN** 系统创建支持按 farm、conversation、session、turn 和时间顺序读取的索引
- **AND** 查询历史消息不得依赖无 `farmId` 前缀的全集合扫描

#### Scenario: agentRecords 索引
- **WHEN** 初始化 `agentRecords` 集合
- **THEN** 系统创建支持按 farm、recordType、cycleId、conversationId 和 createdAt 查询的索引
- **AND** 每日建议缓存与报告历史查询必须命中显式索引

#### Scenario: guardrailsLogs 索引
- **WHEN** 初始化 `guardrailsLogs` 集合
- **THEN** 系统创建支持按 farm、triggerType 和 createdAt 分页查询的索引
- **AND** 是否创建 TTL 索引必须与 Guardrails 现有清理策略保持一致

### Requirement: 第 2 期 Mongo 文档映射
系统 SHALL 将第 2 期 MySQL ORM 行映射为 camelCase Mongo 文档，并保留幂等迁移与回滚所需字段。

#### Scenario: 映射 conversation_messages 行
- **WHEN** 系统将 `conversation_messages` 行写入 MongoDB
- **THEN** 文档必须包含 `mysqlId`、`farmId`、`conversationId`、`sessionId`、`role`、`content`、`contentHash`、`turnId`、`meta` 和 `createdAt`
- **AND** `farmId` 和 `sessionId` 必须来自关联 `conversations` 记录

#### Scenario: 映射 agent_records 行
- **WHEN** 系统将 `agent_records` 行写入 MongoDB
- **THEN** 文档必须包含 `mysqlId`、`farmId`、`userId`、`conversationId`、`cycleId`、`recordType`、`content`、`meta` 和 `createdAt`
- **AND** 不可解析的旧 `meta` 文本必须保存在兼容字段中，避免丢失原始数据

#### Scenario: 映射 guardrails_logs 行
- **WHEN** 系统将 `guardrails_logs` 行写入 MongoDB
- **THEN** 文档必须包含 `mysqlId`、`farmId`、`triggerType`、`triggerDetail`、`sourceTextHash` 和 `createdAt`
- **AND** `sourceText` 必须遵循既有脱敏和截断策略

### Requirement: 第 2 期 Repository 存储后端切换
系统 SHALL 通过 Repository 接口封装第 2 期对象的 MySQL、MongoDB 和双写实现，并通过配置控制每类对象的存储模式。

#### Scenario: 默认使用 MySQL
- **WHEN** 第 2 期对象 storage backend 配置缺省或为 `mysql`
- **THEN** `conversation_messages`、`agent_records` 和 `guardrails_logs` 的读写均使用 MySQL
- **AND** 系统不得要求 MongoDB 可用才能完成这些对象的业务请求

#### Scenario: 双写模式
- **WHEN** 第 2 期对象 storage backend 配置为 `dual`
- **THEN** 系统先写入 MySQL 并以 MySQL 写入结果作为请求成功标准
- **AND** 系统随后写入 MongoDB，失败时记录结构化日志并进入补偿流程

#### Scenario: Mongo 读灰度模式
- **WHEN** 第 2 期对象 storage backend 配置为 `mongo-read`
- **THEN** 系统优先从 MongoDB 读取目标对象
- **AND** MongoDB 读取失败或未命中时系统回退 MySQL
- **AND** 系统记录对象类型、`farmId`、业务 ID 和回退原因

#### Scenario: Mongo 主模式
- **WHEN** 第 2 期对象 storage backend 配置为 `mongo`
- **THEN** 系统使用 MongoDB 作为主要读写后端
- **AND** 进入该模式前必须通过第 2 期对象的一致性校验并完成反向同步预览

### Requirement: 第 2 期多租户隔离
系统 SHALL 在第 2 期 Mongo Repository 层强制所有业务查询包含 `farmId` 过滤。

#### Scenario: conversationMessages 查询
- **WHEN** 服务层查询会话消息列表、最近消息或 turn 关联消息
- **THEN** Repository 方法必须接收 `farm_id`
- **AND** 实际 Mongo 查询条件必须包含 `farmId`

#### Scenario: agentRecords 查询
- **WHEN** 服务层查询建议历史、报告历史、每日缓存或报告分页
- **THEN** Repository 方法必须接收 `farm_id`
- **AND** 实际 Mongo 查询条件必须包含 `farmId`

#### Scenario: guardrailsLogs 查询
- **WHEN** 管理端查询 Guardrails 日志
- **THEN** Repository 必须支持显式 farm 过滤
- **AND** 管理员全局查询必须作为受控运维入口记录审计日志，不得复用普通业务查询方法

### Requirement: 第 2 期 rule_hits 暂缓迁移
系统 SHALL 在第 2 期保持 `agent_turns.rule_hits` 的 MySQL 读写来源，并只记录拆分迁移评估结果。

#### Scenario: 规则引擎写入 rule_hits
- **WHEN** Discovery Rule Engine 更新 turn 的 `rule_hits`
- **THEN** 系统仍写入 MySQL `agent_turns.rule_hits`
- **AND** 本期不得新增运行时必需的 Mongo rule hit 写入

#### Scenario: Data Flywheel 读取 rule_hits
- **WHEN** Data Flywheel 构造样本、问题候选或 judge 输入
- **THEN** 系统仍从 MySQL `AgentTurn.rule_hits` 获取数据
- **AND** 读取行为与第 1 期完成后的行为保持兼容
