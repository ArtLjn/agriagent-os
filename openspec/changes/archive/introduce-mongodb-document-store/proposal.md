## Why

Farm Manager 的 Trace 与 Data Flywheel 表已经出现高密度 JSON 字段、大文本膨胀和 schema 高频演进问题，继续把这些追加型半结构化数据压在 MySQL 中会拖慢备份、查询和迭代速度。

本变更按 `14_MongoDB迁移方案.md` 收敛第 1 期范围：先迁移 `trace_records`、`agent_case_drafts`、`agent_repair_packs`、`agent_review_issue_chains`、`agent_data_flywheel_prelabels` 五张离线/异步路径表，通过 Repository 抽象、双写、回填校验和可回滚切读降低生产风险。

## What Changes

- 新增 MongoDB 文档存储能力，覆盖连接生命周期、集合命名、索引初始化、多租户 `farmId` 过滤和健康检查。
- 为五类第 1 期对象建立 MySQL 与 MongoDB 的 Repository Protocol、Mongo Repository、DualWrite Repository 和依赖注入切换。
- 新增配置开关，支持 `mysql`、`dual`、`mongo-read`、`mongo` 的渐进切换；MySQL 在双写期保持 source of truth。
- 新增 MongoDB 集合初始化脚本，创建 `traceRecords`、`caseDrafts`、`repairPacks`、`reviewIssueChains`、`prelabels` 及必要唯一索引、复合索引和 Trace TTL。
- 扩展迁移工具：提供 MySQL 到 MongoDB 的幂等回填、批量校验、抽样比对、补偿重放与反向回滚脚本入口。
- 增加结构化日志与指标，覆盖 Mongo 写失败、读回退、补偿队列积压、校验不一致率、切读错误率和延迟变化。
- 同步设计文档与数据库文档，明确第 1 期实施边界、第 2/3 期仅作为后续评估，不在本次落地。
- 不删除 MySQL 表，不改变线上业务 API 返回结构，不迁移 `conversation_messages`、`agent_records`、`guardrails_logs`、`agent_turns.rule_hits`。

## Capabilities

### New Capabilities

- `mongodb-document-storage`: MongoDB 文档存储、集合索引、Repository 抽象、双写读回退、多租户隔离和生产切换契约。

### Modified Capabilities

- `database-migration-tooling`: 迁移工具需要支持 MySQL 到 MongoDB 的幂等回填、数据一致性校验、补偿重放和回滚预案。

## Impact

- **后端依赖**: 新增 async MongoDB driver，例如 `motor` 或项目选定的兼容驱动。
- **核心配置**: `backend/config.yaml.example`、settings 模型、应用 lifespan 需要支持 MongoDB URI、数据库名、TLS、超时、连接池和 storage backend 开关。
- **基础设施**: 新增 Mongo client provider、健康检查、集合索引初始化脚本和运维说明。
- **Repository 层**: 影响 Trace、Data Flywheel prelabel、case draft、repair pack、review issue chain 的写入与查询路径。
- **脚本**: 新增 MySQL 到 MongoDB 回填、校验、补偿重放、可选反向同步脚本。
- **测试**: 新增 mapper、Repository、DualWrite、迁移脚本和服务依赖注入测试；现有 API 行为测试必须保持通过。
- **运维**: 需要 MongoDB 连接密钥、白名单/TLS、备份策略、切换 runbook 和回滚阈值。
- **文档**: 同步 `docs/farm-manager-design-spec/01_正式设计/14_MongoDB迁移方案.md`、`10_数据库结构设计.md`、相关运维和迁移规范。
