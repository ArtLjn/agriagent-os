## ADDED Requirements

### Requirement: 第 2 期 MySQL 到 MongoDB 幂等回填
系统 SHALL 扩展 MySQL 到 MongoDB 回填脚本，支持 `conversation_messages`、`agent_records` 和 `guardrails_logs`。

#### Scenario: 回填 conversation_messages
- **WHEN** 开发者运行回填脚本并指定 `conversation_messages`
- **THEN** 脚本按 MySQL 自增主键升序分批读取消息
- **AND** 脚本必须关联 `conversations` 获取 `farmId` 和 `sessionId`
- **AND** 脚本以 `mysqlId` 幂等 upsert 到 `conversationMessages`

#### Scenario: 回填 agent_records
- **WHEN** 开发者运行回填脚本并指定 `agent_records`
- **THEN** 脚本按 MySQL 自增主键升序分批读取记录
- **AND** 脚本将 `meta` 文本规范化为 Mongo 文档或兼容文本字段
- **AND** 脚本以 `mysqlId` 幂等 upsert 到 `agentRecords`

#### Scenario: 回填 guardrails_logs
- **WHEN** 开发者运行回填脚本并指定 `guardrails_logs`
- **THEN** 脚本按 MySQL 自增主键升序分批读取日志
- **AND** 脚本生成 `sourceTextHash` 并执行脱敏或截断策略
- **AND** 脚本以 `mysqlId` 幂等 upsert 到 `guardrailsLogs`

#### Scenario: 重复执行第 2 期回填
- **WHEN** 回填脚本遇到 MongoDB 中已存在相同 `mysqlId` 的文档
- **THEN** 脚本跳过或幂等更新该文档
- **AND** 脚本不得创建重复业务文档

### Requirement: 第 2 期一致性校验
系统 SHALL 扩展一致性校验脚本，在切读 MongoDB 前验证第 2 期对象的行数、缺失 ID、关键字段和列表顺序。

#### Scenario: 校验 conversation_messages
- **WHEN** 开发者运行 `conversation_messages` 一致性校验
- **THEN** 脚本对比 MySQL 行数与 Mongo 文档数
- **AND** 脚本验证 `farmId`、`conversationId`、`sessionId`、`role`、`contentHash`、`turnId`、`meta` 和 `createdAt`
- **AND** 脚本抽样验证按 session 的消息顺序一致

#### Scenario: 校验 agent_records
- **WHEN** 开发者运行 `agent_records` 一致性校验
- **THEN** 脚本对比 MySQL 行数与 Mongo 文档数
- **AND** 脚本验证 `farmId`、`recordType`、`cycleId`、`conversationId`、`content`、`meta` 和 `createdAt`
- **AND** 脚本抽样验证每日建议缓存和报告历史排序一致

#### Scenario: 校验 guardrails_logs
- **WHEN** 开发者运行 `guardrails_logs` 一致性校验
- **THEN** 脚本对比 MySQL 行数与 Mongo 文档数
- **AND** 脚本验证 `farmId`、`triggerType`、`triggerDetail`、`sourceTextHash` 和 `createdAt`
- **AND** 脚本抽样验证按 `trigger_type` 过滤后的分页顺序一致

#### Scenario: 校验失败阻止切读
- **WHEN** 第 2 期一致性校验不一致率超过配置阈值
- **THEN** 校验脚本返回非零退出码
- **AND** 系统不得自动切换对应对象到 `mongo-read` 或 `mongo` 模式

### Requirement: 第 2 期双写补偿重放
系统 SHALL 扩展 Mongo 双写补偿任务和重放工具，支持第 2 期三类对象。

#### Scenario: 创建第 2 期补偿任务
- **WHEN** `dual` 模式下 MySQL 写入成功但 MongoDB 写入失败
- **THEN** 系统创建包含对象类型、`farmId`、`mysqlId`、业务关联字段、错误 code 和脱敏错误摘要的补偿任务
- **AND** 主业务请求仍以 MySQL 写入结果为准

#### Scenario: 重放 conversation_messages 补偿
- **WHEN** 补偿工具处理 `conversation_messages` 任务
- **THEN** 工具从 MySQL 重新加载消息及关联 conversation
- **AND** 工具幂等写入 `conversationMessages`

#### Scenario: 重放 agent_records 补偿
- **WHEN** 补偿工具处理 `agent_records` 任务
- **THEN** 工具从 MySQL 重新加载 AgentRecord
- **AND** 工具幂等写入 `agentRecords`

#### Scenario: 重放 guardrails_logs 补偿
- **WHEN** 补偿工具处理 `guardrails_logs` 任务
- **THEN** 工具从 MySQL 重新加载 GuardrailsLog
- **AND** 工具幂等写入 `guardrailsLogs`

### Requirement: 第 2 期 Mongo 到 MySQL 反向同步预案
系统 SHALL 为第 2 期对象进入 Mongo 主模式后的紧急回滚提供 Mongo 到 MySQL 的反向同步预览入口。

#### Scenario: 反向同步预览
- **WHEN** 运维准备将第 2 期对象从 `mongo` 模式回滚到 MySQL
- **THEN** 反向同步脚本按集合扫描 Mongo 文档
- **AND** 脚本输出 MySQL 缺失记录、落后记录和关键字段冲突
- **AND** 脚本默认不得静默覆盖 MySQL 数据

#### Scenario: conversationMessages 反向同步冲突
- **WHEN** Mongo 消息文档与 MySQL 消息行同时存在且 `contentHash`、`role` 或 `conversationId` 冲突
- **THEN** 脚本记录冲突详情并要求人工确认处理

#### Scenario: agentRecords 反向同步冲突
- **WHEN** Mongo AgentRecord 文档与 MySQL 行同时存在且 `recordType`、`content` 或 `meta` 冲突
- **THEN** 脚本记录冲突详情并要求人工确认处理

#### Scenario: guardrailsLogs 反向同步冲突
- **WHEN** Mongo GuardrailsLog 文档与 MySQL 行同时存在且 `triggerType` 或 `sourceTextHash` 冲突
- **THEN** 脚本记录冲突详情并要求人工确认处理

### Requirement: 第 2 期迁移审计报告
系统 SHALL 在实施前后产出第 2 期迁移审计信息，覆盖表结构、代码路径、API 影响面、测试覆盖和暂缓项。

#### Scenario: 实施前审计
- **WHEN** 开发者开始第 2 期实现
- **THEN** 任务必须记录三张实施表的 MySQL 字段、索引、外键、主要读写函数、API 和测试文件
- **AND** 任务必须记录 `agent_turns.rule_hits` 只评估不实施的原因

#### Scenario: 实施后审计
- **WHEN** 第 2 期实现完成
- **THEN** 任务必须使用代码搜索审计目标表的直接 SQLAlchemy 读写点
- **AND** 对保留直查的路径必须记录原因、风险和后续处理建议
