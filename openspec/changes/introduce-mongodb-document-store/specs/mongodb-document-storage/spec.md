## ADDED Requirements

### Requirement: MongoDB 连接与健康检查
系统 SHALL 提供统一 MongoDB 连接配置、异步 client 生命周期管理和健康检查能力。

#### Scenario: 应用启动初始化 Mongo client
- **WHEN** 配置中启用 MongoDB 且应用启动
- **THEN** 系统创建共享 MongoDB client 并使用配置中的 URI、数据库名、TLS、连接池大小和超时参数
- **AND** 系统不得在业务请求内重复创建 MongoDB client

#### Scenario: MongoDB 健康检查
- **WHEN** 运维或应用健康检查调用 MongoDB health check
- **THEN** 系统执行轻量 ping 并返回连接状态、数据库名和错误上下文
- **AND** 错误日志不得输出明文密码或完整连接串

### Requirement: 第 1 期 Mongo 集合与索引初始化
系统 SHALL 为第 1 期迁移对象创建 MongoDB 集合与索引，覆盖 `traceRecords`、`caseDrafts`、`repairPacks`、`reviewIssueChains` 和 `prelabels`。

#### Scenario: 初始化集合索引
- **WHEN** 开发者运行 MongoDB 索引初始化脚本
- **THEN** 系统为每个集合创建 `{ mysqlId: 1 }` 唯一索引
- **AND** 系统为业务 ID 创建唯一或查询索引，包括 `requestId`、`draftId`、`packId`、`chainId`、`sampleId`
- **AND** 系统为租户查询创建以 `farmId` 为前缀的复合索引

#### Scenario: Trace TTL 索引
- **WHEN** 初始化 `traceRecords` 集合
- **THEN** 系统在 `createdAt` 上创建 TTL 索引
- **AND** 系统不得为 Data Flywheel 的四个集合创建默认 TTL 删除策略

### Requirement: Mongo 文档映射
系统 SHALL 将 MySQL ORM 行映射为 camelCase Mongo 文档，并保留幂等迁移与回滚所需字段。

#### Scenario: TraceRecord 映射为 traceRecords 文档
- **WHEN** 系统将 `trace_records` 行写入 MongoDB
- **THEN** 文档包含 `mysqlId`、`farmId`、`requestId`、`sessionId`、`conversationMessageId`、`input`、`output`、`tokenUsage`、`startTime`、`endTime`、`durationMs` 和 `createdAt`
- **AND** `mysqlId` 等于原 MySQL `trace_records.id`

#### Scenario: Data Flywheel 行映射为文档
- **WHEN** 系统将 Data Flywheel 第 1 期对象写入 MongoDB
- **THEN** 文档保留原 MySQL 主键为 `mysqlId`
- **AND** 文档保留对应业务 ID 字段，包括 `draftId`、`packId`、`chainId` 或 `sampleId`
- **AND** 原 JSON 字段以嵌套文档或数组保存，不得序列化为不可查询的 JSON 字符串

### Requirement: Repository 存储后端切换
系统 SHALL 通过 Repository 接口封装 MySQL、MongoDB 和双写实现，并通过配置控制每类对象的存储模式。

#### Scenario: 默认使用 MySQL
- **WHEN** storage backend 配置为 `mysql`
- **THEN** Trace 和 Data Flywheel 第 1 期对象的读写均使用现有 MySQL 实现
- **AND** 系统不得连接 MongoDB 作为该对象的必要依赖

#### Scenario: 双写模式
- **WHEN** storage backend 配置为 `dual`
- **THEN** 系统先写入 MySQL 并以 MySQL 写入结果作为请求成功标准
- **AND** 系统随后写入 MongoDB，失败时记录结构化日志并进入补偿流程

#### Scenario: Mongo 读灰度模式
- **WHEN** storage backend 配置为 `mongo-read`
- **THEN** 系统优先从 MongoDB 读取目标对象
- **AND** MongoDB 读取失败或未命中时系统回退 MySQL
- **AND** 系统记录读回退原因、对象类型和业务 ID

#### Scenario: Mongo 主模式
- **WHEN** storage backend 配置为 `mongo`
- **THEN** 系统对目标对象使用 MongoDB 作为主要读写后端
- **AND** 进入该模式前必须存在已通过的数据一致性校验记录

### Requirement: 多租户 farmId 隔离
系统 SHALL 在 Mongo Repository 层强制所有业务查询包含 `farmId` 过滤。

#### Scenario: 查询目标对象
- **WHEN** 服务层通过 Mongo Repository 查询列表、详情或更新对象
- **THEN** Repository 方法必须接收 `farm_id`
- **AND** 实际 Mongo 查询条件必须包含 `farmId`

#### Scenario: 拒绝缺少租户的业务查询
- **WHEN** 调用方无法提供 `farm_id`
- **THEN** Repository 必须拒绝执行业务查询并返回带 code 字段的错误

### Requirement: 双写补偿与可观测性
系统 SHALL 对 MongoDB 写失败、读回退、补偿重放和一致性异常输出结构化日志和指标。

#### Scenario: Mongo 二级写失败
- **WHEN** 双写模式下 MySQL 写入成功但 MongoDB 写入失败
- **THEN** 系统记录 `mongo_secondary_write_failed` 日志
- **AND** 日志包含对象类型、`farmId`、业务 ID、`mysqlId` 和脱敏后的错误上下文
- **AND** 系统创建可重放的补偿任务

#### Scenario: 补偿重放成功
- **WHEN** 补偿任务重放成功写入 MongoDB
- **THEN** 系统记录重放成功日志并标记补偿任务完成

#### Scenario: 一致性异常告警
- **WHEN** 数据校验发现不一致率超过配置阈值
- **THEN** 系统输出错误日志并阻止自动进入 `mongo-read` 或 `mongo` 模式
