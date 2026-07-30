## Why

第 1 期 MongoDB 文档存储已经覆盖 Trace 与 Data Flywheel 五类高 JSON 密度对象，并完成索引、回填、校验、双写和启动验证。第 2 期需要把在线对话消息、Agent 输出记录和 Guardrails 追加日志纳入同一套灰度迁移体系，继续降低 MySQL 大文本、JSON 文本和备份体积压力，同时保持 MySQL 回滚基准。

## What Changes

- 盘点并迁移 `conversation_messages`、`agent_records`、`guardrails_logs` 三张第 2 期建议迁移表，覆盖 MySQL 表结构、代码读写路径、API 影响面和现有测试覆盖。
- 新增第 2 期 Mongo 集合 schema 与索引：`conversationMessages`、`agentRecords`、`guardrailsLogs`，保留 `mysqlId`、`farmId`、业务关联字段和时间字段。
- 为三类对象建立 Repository Protocol、MySQL Repository、Mongo Repository、DualWrite Repository 与 mapper，继续支持 `mysql -> dual -> mongo-read -> mongo` 灰度路线。
- 扩展现有 Mongo 索引初始化、回填、校验、补偿重放和反向同步预案，支持第 2 期三张表。
- 保持线上 API contract 不变，`/agent/conversations`、`/agent/conversations/{session_id}/messages`、`/agent/conversations/{session_id}/debug-export`、报告历史接口和 `/admin/guardrails-logs` 返回结构保持兼容。
- 保留 `conversations`、`feedback_records`、`token_daily_stats`、`agent_data_flywheel_labels` 和第 1 期 MySQL 表作为 MySQL 回滚基准，不做删表。
- `agent_turns.rule_hits` 本次只做拆分迁移评估：输出字段、读写路径、索引收益、数据一致性风险和后续建议，不进入第 2 期实施。
- 不修改 `backend/config.yaml` 中真实运行密钥，不提交 MongoDB URI、密码、token 或其他敏感信息。

## Capabilities

### New Capabilities

- `mongodb-online-document-phase-2`: 第 2 期在线文档对象迁移，覆盖对话消息、Agent 输出记录、Guardrails 日志的 Mongo schema、Repository 切换、API 兼容、灰度和回滚契约。

### Modified Capabilities

- `mongodb-document-storage`: 扩展 MongoDB 文档存储能力，从第 1 期五类对象扩展到第 2 期三类在线追加对象，并明确 `agent_turns.rule_hits` 只评估不迁移。
- `database-migration-tooling`: 扩展 MySQL 到 MongoDB 回填、校验、补偿重放和反向同步工具，支持第 2 期三张表并保留 MySQL source of truth。

## Impact

- **MySQL 表结构**: `conversation_messages` 包含 `content` 大文本、`meta` 文本 JSON、`meta_json` JSON、`turn_id` 和 `content_hash`；`agent_records` 包含 `content` 大文本和 `meta` 文本 JSON；`guardrails_logs` 是追加型拦截日志；`agent_turns.rule_hits` 在 ORM 中为 JSON 字段但本次仅评估。
- **后端代码路径**: 影响 `app.services.conversation_service`、`app.agent.application.history_use_case`、`app.services.agent_service`、`app.agent.application.chat_use_case`、`app.services.daily_advice_generation`、`app.services.agent_report_service`、`app.api.admin`、`app.agent.guardrails.rules`、`app.services.session_debug_export_service` 和 Data Flywheel 对 `rule_hits` 的读取路径。
- **API 影响面**: `/agent/chat`、`/agent/chat/stream` 的会话消息与 `AgentRecord` 写入，`/agent/conversations`、`/agent/conversations/{session_id}/messages`、`/agent/conversations/{session_id}/debug-export`、建议/报告历史、报告分页和 `/admin/guardrails-logs`。
- **测试覆盖**: 现有覆盖包括 `test_conversation_service.py`、`test_agent_api.py`、`test_agent_models.py`、`test_agent_record.py`、`test_advice_cache.py`、`test_daily_advice_generation.py`、`test_agent_turn_service.py`、`test_session_debug_export_service.py`、`test_mongo_indexes.py`、`test_mongo_mappers.py`、`test_mongo_migration_tooling.py`、`test_mongo_compensation.py` 和 Data Flywheel API/服务测试；第 2 期需补充 Repository、mapper、双写、回填校验和 API 兼容测试。
- **配置与运维**: 只扩展示例配置和 settings 默认值，不修改真实 `backend/config.yaml` 密钥；灰度按对象独立切换，异常时立即回到 `mysql` 或 `dual`。
- **文档**: 更新 MongoDB 迁移方案、runbook、文档存储状态和第 2 期评估结论。
