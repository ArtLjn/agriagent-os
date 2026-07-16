## 1. 依赖、配置与连接基础

- [x] 1.1 在 `backend/requirements.txt` 中添加 async MongoDB driver，并安装验证导入正常
- [x] 1.2 扩展 settings 模型，新增 MongoDB URI、数据库名、TLS、连接池、超时和 storage backend 配置
- [x] 1.3 更新 `backend/config.yaml.example`，提供脱敏 MongoDB 配置示例和五类对象默认 `mysql` backend
- [x] 1.4 新增统一 Mongo client provider，支持应用启动初始化、关闭释放和连接串脱敏日志
- [x] 1.5 新增 MongoDB health check，覆盖 ping 成功、连接失败和错误脱敏

## 2. 集合 Schema、索引与映射器

- [x] 2.1 新增 Mongo 集合索引初始化脚本，创建五个集合的唯一索引、farmId 复合索引和 trace TTL
- [x] 2.2 为 `TraceRecord` 实现 MySQL 行到 `traceRecords` 文档的 mapper 和反向 mapper
- [x] 2.3 为 `AgentCaseDraft`、`AgentRepairPack`、`AgentReviewIssueChain`、`AgentDataFlywheelPrelabel` 实现 mapper 和反向 mapper
- [x] 2.4 为 mapper 添加单元测试，覆盖字段命名、`mysqlId`、`farmId`、时间字段和 JSON 规范化
- [x] 2.5 运行索引脚本的 dry-run 或集成测试，确认重复执行幂等

## 3. Repository 抽象与实现

- [x] 3.1 为 Trace 定义 Repository Protocol，覆盖写入、按 request_id 查询、按 session 列表和按 node 聚合所需方法
- [x] 3.2 为 Trace 实现 MySQL Repository、Mongo Repository 和 DualWrite Repository
- [x] 3.3 为 Data Flywheel 四类对象定义 Repository Protocol，覆盖当前服务层用到的创建、详情、列表、更新和去重查询
- [x] 3.4 为 Data Flywheel 四类对象实现 MySQL Repository、Mongo Repository 和 DualWrite Repository
- [x] 3.5 在 Mongo Repository 中强制所有业务查询接收 `farm_id` 并包含 `farmId` 条件
- [x] 3.6 为 Repository 添加单元测试，覆盖 `mysql`、`dual`、`mongo-read` 和 `mongo` 模式下的读写行为

## 4. 双写补偿与可观测性

- [x] 4.1 设计并实现 Mongo 写失败补偿任务存储，记录对象类型、`farmId`、业务 ID、`mysqlId`、错误摘要和状态
- [x] 4.2 实现补偿重放服务或命令，从 MySQL 重新加载对象并幂等写入 MongoDB
- [x] 4.3 为双写失败、读回退、补偿成功和补偿失败添加结构化日志
- [x] 4.4 添加配置化阈值，用于 Mongo 写失败率、读错误率和一致性不一致率判断
- [x] 4.5 为补偿任务和结构化日志添加测试，确保错误信息包含 code 和上下文且不泄露连接串

## 5. 服务接入与后端切换

- [x] 5.1 将 `TraceDAO` 写入路径改为通过 Trace Repository，并保持 token daily stats 仍写 MySQL
- [x] 5.2 将 admin trace 查询路径接入 Trace Repository，`mongo-read` 未命中或失败时回退 MySQL
- [x] 5.3 将 Data Flywheel prelabel 读写路径接入对应 Repository
- [x] 5.4 将 case draft 创建与查询路径接入对应 Repository
- [x] 5.5 将 repair pack 创建、列表、详情、状态回写和去重查询路径接入对应 Repository
- [x] 5.6 将 review issue chain 保存、列表、详情和状态更新路径接入对应 Repository
- [x] 5.7 使用 `rg` 审计五张目标表的直接 SQLAlchemy 查询，记录暂不迁移的查询及原因

### 5.7 直接查询审计备注

- `backend/app/modules/data_flywheel/document_repository_mysql.py` 和 `backend/app/infra/trace_repository.py`：MySQL Repository 的 source-of-truth 实现，保留直接 SQLAlchemy 查询。
- `backend/app/api/admin_trace.py`：`farm_id` 存在时列表查询走 Trace Repository；无 `farm_id` 的列表、timeline、diagnostics、node detail 和 delete 为兼容/运维入口，因 Mongo Repository 强制 farmId 暂保留 MySQL 查询。
- `backend/app/infra/trace_cleaner.py`、`backend/app/api/admin_stats.py`、`backend/app/agent/application/chat_use_case.py`、`backend/app/evaluation/discovery/rule_engine.py`、`backend/app/simulation/test_runner.py`、`backend/app/modules/data_flywheel/review_issue_chain_helpers.py`：清理、统计、诊断、发现规则和模拟器辅助查询，不属于本组主读写切换路径，暂保留 MySQL 查询。
- `backend/app/modules/data_flywheel/review_issue_chain_service.py`：无 `session_id` 的全量 persisted chain 合并需要跨 session 列表能力，当前 Repository 仅覆盖按 session 列表；带 `session_id` 的列表和 session count 已接入 Repository。

## 6. MySQL 到 MongoDB 迁移工具

- [x] 6.1 新增 MySQL 到 MongoDB 回填脚本，支持按表名、batch size、起始 ID 和时间范围执行
- [x] 6.2 回填脚本以 `mysqlId` 幂等 upsert，输出扫描、写入、跳过和失败数量
- [x] 6.3 新增一致性校验脚本，覆盖 count、缺失 `mysqlId`、关键字段抽样和 JSON 规范化比对
- [x] 6.4 校验脚本在不一致率超过阈值时返回非零退出码，并输出差异报告路径
- [x] 6.5 新增 Mongo 到 MySQL 反向同步脚本入口，用于进入 `mongo` 模式后的紧急回滚预案
- [x] 6.6 为回填、校验和反向同步核心逻辑添加测试，避免依赖真实生产数据库

## 7. 测试、灰度与验证

- [x] 7.1 增加 Mongo Repository 集成测试 fixture，使用测试库或可替代的 Mongo 测试方案
- [x] 7.2 运行 Trace 相关后端测试，覆盖写入、列表、详情、清理和 admin trace API
- [x] 7.3 运行 Data Flywheel 相关后端测试，覆盖 prelabel、case draft、repair pack 和 review issue chain
- [x] 7.4 运行迁移脚本测试和一致性校验测试
- [x] 7.5 运行 `ruff check . && ruff format .`
- [x] 7.6 运行 `bash scripts/check-complexity-budget.sh`
- [x] 7.7 运行 `openspec validate introduce-mongodb-document-store --type change --strict`

## 8. 文档与上线 Runbook

- [x] 8.1 更新 MongoDB 迁移方案说明，同步最终集合、索引、配置和切换步骤
- [x] 8.2 更新数据库结构说明，标注五张表的 Mongo 双写/切读状态
- [x] 8.3 更新数据库与迁移规范，补充 Mongo 回填、校验、回滚和多租户查询要求
- [x] 8.4 编写生产灰度 runbook，包含 `mysql -> dual -> mongo-read -> mongo` 命令、观察指标和回滚阈值
- [x] 8.5 记录第 2 期和第 3 期暂缓项，避免本次实施迁移对话消息或 `agent_turns.rule_hits`

### 8.x 文档落点说明

当前 worktree 中 `docs/farm-manager-design-spec/` 为空目录，未包含正式设计文档源文件；本次可交付文档落在 `docs/database/mongodb-migration-runbook.md` 与 `docs/database/mongodb-document-storage.md`。
