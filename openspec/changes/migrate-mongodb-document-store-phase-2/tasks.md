## 1. 盘点与实施边界确认

- [x] 1.1 记录 `conversation_messages`、`agent_records`、`guardrails_logs` 的 MySQL 字段、索引、外键和现有数据量
- [x] 1.2 使用 `rg` 审计三张实施表的直接 SQLAlchemy 读写路径，覆盖 service、use case、API、清理任务、测试和脚本
- [x] 1.3 记录 API 影响面：聊天、流式聊天、会话列表、消息列表、debug export、建议历史、报告历史、报告分页和 `/admin/guardrails-logs`
- [x] 1.4 记录现有测试覆盖清单，并标注需要新增或改造的测试文件
- [x] 1.5 明确本期实施 `conversation_messages`、`agent_records`、`guardrails_logs`，并记录 `agent_turns.rule_hits` 只做评估不迁移

## 2. 配置、索引与文档模型

- [x] 2.1 扩展 settings 与示例配置，新增三类对象 storage backend，默认均为 `mysql`
- [x] 2.2 确认不修改 `backend/config.yaml` 中真实运行密钥，只更新脱敏示例和文档
- [x] 2.3 扩展 Mongo 索引初始化脚本，加入 `conversationMessages`、`agentRecords`、`guardrailsLogs`
- [x] 2.4 为三类集合创建 `{ mysqlId: 1 }` 唯一索引和以 `farmId` 为前缀的查询索引
- [x] 2.5 为 Guardrails 日志确认 TTL 或应用清理策略，并与现有 30 天清理逻辑对齐
- [x] 2.6 为索引计划添加 dry-run 和幂等测试

## 3. Mapper 与 Repository 抽象

- [x] 3.1 实现 `conversation_messages` MySQL 行与 `conversationMessages` 文档的 mapper，包含 `farmId`、`sessionId`、`meta` 和 `legacyMetaText`
- [x] 3.2 实现 `agent_records` MySQL 行与 `agentRecords` 文档的 mapper，兼容可解析和不可解析 `meta`
- [x] 3.3 实现 `guardrails_logs` MySQL 行与 `guardrailsLogs` 文档的 mapper，包含 `sourceTextHash` 和脱敏/截断策略
- [x] 3.4 为三个 mapper 添加单元测试，覆盖字段命名、时间字段、`mysqlId`、`farmId`、JSON 规范化和反向映射
- [x] 3.5 定义 `ConversationMessageRepository` Protocol，覆盖保存、批量保存、最近消息、按 session 列表、按 ID 和按 turn 查询
- [x] 3.6 定义 `AgentRecordRepository` Protocol，覆盖创建、删除每日缓存、建议历史、报告历史、报告分页、每日缓存查询和 cycle 引用清理
- [x] 3.7 定义 `GuardrailsLogRepository` Protocol，覆盖创建、管理员分页查询和旧日志清理
- [x] 3.8 实现三类 MySQL Repository，行为保持与现有 SQLAlchemy 逻辑一致
- [x] 3.9 实现三类 Mongo Repository，强制业务查询接收 `farm_id` 并包含 `farmId` 条件
- [x] 3.10 实现三类 DualWrite Repository，MySQL 主写、Mongo 二级写失败进入补偿队列

## 4. 服务接入与 API 兼容

- [x] 4.1 将 `conversation_service.save_message()`、`save_messages_batch()`、`get_recent_messages()` 和 `get_conversation_messages()` 接入 ConversationMessage Repository
- [x] 4.2 将历史消息、会话摘要生成、debug export 和 Data Flywheel 消息读取路径接入 ConversationMessage Repository
- [x] 4.3 将聊天、流式回复、每日建议、报告生成中的 AgentRecord 创建接入 AgentRecord Repository
- [x] 4.4 将建议历史、报告历史、报告分页、每日建议缓存读取和刷新删除接入 AgentRecord Repository
- [x] 4.5 将农场和种植周期服务中清理 AgentRecord `cycle_id` 的路径接入 AgentRecord Repository
- [x] 4.6 将 `/admin/guardrails-logs` 和 Guardrails 旧日志清理接入 GuardrailsLog Repository
- [x] 4.7 确认 `/agent/chat`、`/agent/chat/stream`、历史消息、debug export、建议历史、报告历史和 Guardrails 管理接口响应结构不变
- [x] 4.8 使用 `rg` 复查三张目标表剩余直查路径，并记录保留原因和风险

## 5. 回填、校验、补偿与回滚

- [x] 5.1 扩展 `scripts/migrate_mysql_to_mongo.py backfill` 支持三张第 2 期表
- [x] 5.2 回填 `conversation_messages` 时 join `conversations` 获取 `farmId` 和 `sessionId`
- [x] 5.3 回填 `agent_records` 时规范化 `meta`，不可解析文本保留兼容字段
- [x] 5.4 回填 `guardrails_logs` 时生成 `sourceTextHash` 并执行脱敏/截断
- [x] 5.5 扩展 `verify` 支持三张第 2 期表，覆盖 count、缺失 `mysqlId`、关键字段抽样和列表顺序校验
- [x] 5.6 扩展补偿重放服务，支持三类对象从 MySQL source of truth 重新加载并幂等写入 Mongo
- [x] 5.7 扩展 `reverse-sync` 预览，输出三类对象 MySQL 缺失、落后和冲突记录，不静默覆盖 MySQL
- [x] 5.8 为回填、校验、补偿和反向同步核心逻辑添加不依赖生产数据库的测试

## 6. agent_turns.rule_hits 评估

- [x] 6.1 盘点 `AgentTurn.rule_hits` 写入路径，包括 rule engine、`finish_turn()` 和 `mark_event_range()`
- [x] 6.2 盘点 `rule_hits` 读取路径，包括 Data Flywheel 样本、问题候选、问题链、judge worker 和相关测试
- [x] 6.3 统计或设计统计脚本，评估 `rule_hits` 空数组比例、平均长度、最大长度和与风险字段的查询耦合度
- [x] 6.4 输出 `rule_hits` 拆分迁移评估文档，给出继续留 MySQL、拆为 `agentTurnRuleHits` 集合或样本物化的建议
- [x] 6.5 确认第 2 期实现不改变 `agent_turns.rule_hits` 运行时读写来源

## 7. 测试、灰度与验证

- [x] 7.1 新增或更新 ConversationMessage Repository 测试，覆盖 `mysql`、`dual`、`mongo-read`、`mongo` 四种模式
- [x] 7.2 新增或更新 AgentRecord Repository 测试，覆盖每日缓存、报告历史、分页和 cycle 清理
- [x] 7.3 新增或更新 GuardrailsLog Repository 测试，覆盖分页过滤、清理和 Mongo 读回退
- [x] 7.4 更新 API 行为测试，确保历史消息、debug export、报告历史和 Guardrails 管理接口兼容
- [x] 7.5 更新迁移工具、索引、mapper、补偿和回滚预览测试
- [x] 7.6 运行相关后端测试：conversation、agent record、daily advice、report、guardrails、Data Flywheel、Mongo tooling
- [x] 7.7 运行 `ruff check . && ruff format .`
- [x] 7.8 运行 `bash scripts/check-complexity-budget.sh`
- [x] 7.9 运行 `openspec validate migrate-mongodb-document-store-phase-2 --type change --strict`

## 8. 文档与上线 Runbook

- [ ] 8.1 更新 `farm-manager-design-spec/01_正式设计/14_MongoDB迁移方案.md`，同步第 2 期范围、状态和 `rule_hits` 评估结论
- [x] 8.2 更新 `docs/database/mongodb-migration-runbook.md`，加入三张第 2 期表的索引、回填、校验、灰度和回滚命令
- [x] 8.3 更新 `docs/database/mongodb-document-storage.md`，记录第 2 期集合、默认模式、索引策略和暂缓项
- [x] 8.4 记录生产灰度顺序：`guardrails_logs -> agent_records -> conversation_messages`
- [x] 8.5 记录回滚阈值：读错误率、写失败率、补偿积压、一致性不一致率和接口 P99 延迟
- [x] 8.6 明确第 2 期不删 MySQL 表，不关闭 MySQL 写入，不提交敏感配置
