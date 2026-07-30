## ADDED Requirements

### Requirement: 清库候选范围
系统 SHALL 只允许清理已经迁移到 MongoDB 且满足清理前置条件的 MySQL 文档表数据。

#### Scenario: 候选表允许进入清理计划
- **WHEN** 开发者运行 MySQL 文档存储清理计划
- **THEN** 系统包含 `trace_records`、`agent_case_drafts`、`agent_repair_packs`、`agent_review_issue_chains`、`agent_data_flywheel_prelabels`、`conversation_messages`、`agent_records` 和 `guardrails_logs`
- **AND** 系统必须为每张表展示 MySQL 行数、Mongo 文档数、storage backend 和清理状态

#### Scenario: 禁止清理未迁移关系表
- **WHEN** 开发者请求清理 `conversations`、`agent_turns`、`feedback_records`、`token_daily_stats` 或 `agent_data_flywheel_labels`
- **THEN** 系统必须拒绝执行
- **AND** 错误必须包含 `code=MYSQL_CLEANUP_TABLE_NOT_ALLOWED`

### Requirement: 清理前置条件
系统 SHALL 在删除或瘦身任何 MySQL 数据前验证 Mongo 主模式、数据一致性、补偿队列、反向同步预览和备份。

#### Scenario: storage backend 未进入 mongo
- **WHEN** 目标对象 storage backend 为 `mysql`、`dual` 或 `mongo-read`
- **THEN** 清理命令必须失败
- **AND** 错误必须包含目标表、当前 backend 和 `code=MYSQL_CLEANUP_BACKEND_NOT_MONGO`

#### Scenario: 一致性校验未通过
- **WHEN** 最近一次 Mongo 一致性校验缺失或失败
- **THEN** 清理命令必须失败
- **AND** 系统必须提示先运行对应表的 `verify`

#### Scenario: 补偿队列存在积压
- **WHEN** `mongo_compensation_tasks` 中目标对象存在 pending 或 failed 任务
- **THEN** 清理命令必须失败
- **AND** 系统必须输出积压数量和对象类型

#### Scenario: 缺少备份文件
- **WHEN** 开发者执行真实清理但未提供备份文件
- **THEN** 清理命令必须失败
- **AND** 系统不得删除任何 MySQL 数据

### Requirement: 默认 dry-run
系统 SHALL 默认以 dry-run 模式运行清理命令，只有显式执行参数和人工确认齐全时才允许修改 MySQL。

#### Scenario: 默认清理不删除数据
- **WHEN** 开发者运行清理命令且未传入 `--execute`
- **THEN** 系统只输出将清理的行数、批次和风险提示
- **AND** MySQL 数据不得发生变化

#### Scenario: execute 需要确认 token
- **WHEN** 开发者传入 `--execute` 但缺少有效确认 token
- **THEN** 系统必须拒绝执行
- **AND** 错误必须包含 `code=MYSQL_CLEANUP_CONFIRMATION_REQUIRED`

### Requirement: conversation_messages 安全瘦身
系统 SHALL 对 `conversation_messages` 采用引用安全策略，不得在仍有 MySQL 外键依赖时直接删除消息行。

#### Scenario: 外键仍依赖 conversation_messages
- **WHEN** `agent_turns`、`feedback_records` 或其他表仍引用 `conversation_messages.id`
- **THEN** 系统不得直接删除 `conversation_messages` 行
- **AND** 系统只能执行已验证的大字段瘦身策略或返回 blocked 状态

#### Scenario: 执行消息大字段瘦身
- **WHEN** 清理策略为 `slim` 且前置条件全部通过
- **THEN** 系统保留 `id`、`conversation_id`、`role`、`turn_id`、`content_hash` 和 `created_at`
- **AND** 系统必须清理或归档 `content`、`meta`、`meta_json` 等大字段

### Requirement: 清理审计与回滚
系统 SHALL 为每次清理生成审计报告，并提供从备份恢复 MySQL 数据的回滚入口。

#### Scenario: 生成清理审计报告
- **WHEN** 清理 dry-run 或 execute 完成
- **THEN** 系统必须生成包含表名、模式、行数、Mongo 文档数、备份 SHA256、删除或瘦身数量、执行时间和执行结果的报告
- **AND** 报告不得包含明文连接串、API key 或大文本正文

#### Scenario: 从备份回滚导入
- **WHEN** 运维执行 `rollback-import` 并提供有效备份文件
- **THEN** 系统必须恢复目标表数据
- **AND** 恢复后必须运行一致性校验并输出报告
