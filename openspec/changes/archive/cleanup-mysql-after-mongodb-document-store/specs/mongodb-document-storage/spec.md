## ADDED Requirements

### Requirement: MongoDB 文档存储清理阶段
系统 SHALL 在 `mysql -> dual -> mongo-read -> mongo` 后新增 `mysql-cleanup` 生命周期阶段，用于清理已迁移对象在 MySQL 中的文档型历史数据。

#### Scenario: 对象进入 mysql-cleanup 阶段
- **WHEN** 某类文档对象已在 `mongo` 模式稳定运行并通过清理前置检查
- **THEN** 系统允许该对象进入 `mysql-cleanup` 阶段
- **AND** MySQL 不再作为该对象的实时回滚基准

#### Scenario: 清理后仍保持 API 稳定 ID
- **WHEN** 对象进入 `mysql-cleanup` 阶段
- **THEN** API 仍必须使用稳定业务 ID 或原 `mysqlId`
- **AND** 系统不得向客户端暴露 Mongo `_id` 作为替代

### Requirement: 清理后的 MySQL 保留边界
系统 SHALL 区分可清理的文档型数据和必须保留的关系型数据。

#### Scenario: 保留关系型会话骨架
- **WHEN** 清理第 2 期聊天相关数据
- **THEN** 系统必须保留 `conversations` 表
- **AND** 系统不得清理 `agent_turns.rule_hits`

#### Scenario: 保留不可迁移评估数据
- **WHEN** 执行 MongoDB 文档存储清理
- **THEN** 系统必须保留 `agent_turns`、`feedback_records`、`token_daily_stats` 和 `agent_data_flywheel_labels`
- **AND** 清理工具必须拒绝这些表名

### Requirement: 清理后运行模式约束
系统 SHALL 确保清理后的对象不会被配置回依赖 MySQL 原始数据的模式，除非先完成回滚导入。

#### Scenario: 已清理对象禁止切回 mysql
- **WHEN** 某对象已完成 MySQL 清理且未执行回滚导入
- **THEN** 系统不得允许该对象 storage backend 切回 `mysql`
- **AND** 运维文档必须提示先执行 `rollback-import`

#### Scenario: 已清理对象继续使用 mongo 主模式
- **WHEN** 清理后服务启动
- **THEN** 已清理对象必须继续使用 Mongo Repository 作为主读写后端
- **AND** 启动检查必须对配置不一致给出结构化错误
