## 1. 清理前盘点

- [x] 1.1 盘点第 1 期五张文档表和第 2 期三张文档表的 MySQL 行数、Mongo 文档数、最近 verify 结果和 storage backend
- [x] 1.2 盘点 `conversation_messages` 的外键和逻辑引用，覆盖 `agent_turns`、`feedback_records`、`trace_records`、Data Flywheel、debug export 和测试
- [x] 1.3 明确三期禁止清理表：`conversations`、`agent_turns`、`feedback_records`、`token_daily_stats`、`agent_data_flywheel_labels`
- [x] 1.4 设计每张候选表的清理策略：全量删除、分批删除、过期清理或大字段瘦身
- [x] 1.5 记录执行前置条件：Mongo 主模式、补偿队列清零、verify 通过、reverse-sync 无冲突、备份完成

## 2. 清理工具实现

- [x] 2.1 新增 `scripts/cleanup_mysql_document_store.py` 或扩展 `scripts/migrate_mysql_to_mongo.py cleanup` 子命令
- [x] 2.2 实现 `plan` 命令，输出候选表、禁止表、行数、Mongo 文档数、backend、verify 状态、补偿状态和 blocked 原因
- [x] 2.3 实现 `backup` 命令，按主键升序导出 JSONL 或 SQL dump，并生成 SHA256 和元数据
- [x] 2.4 实现 `cleanup --dry-run`，输出预计清理行数、批次、策略和风险，不修改数据库
- [x] 2.5 实现 `cleanup --execute`，要求 `--table`、`--backup-file`、`--confirm-token` 和显式策略
- [x] 2.6 实现分批删除/瘦身执行器，支持 batch size、sleep interval、进度日志和失败停止
- [x] 2.7 实现 `post-verify`，验证 Mongo 文档完整性和 MySQL 清理结果
- [x] 2.8 实现 `rollback-import`，从备份恢复 MySQL 数据并避免重复主键插入

## 3. 安全保护与策略

- [x] 3.1 实现候选表白名单和禁止表黑名单，禁止表请求返回 `MYSQL_CLEANUP_TABLE_NOT_ALLOWED`
- [x] 3.2 实现 backend 检查，未进入 `mongo` 的对象返回 `MYSQL_CLEANUP_BACKEND_NOT_MONGO`
- [x] 3.3 实现 verify 报告检查，缺少或失败时阻止 execute
- [x] 3.4 实现补偿队列检查，目标对象存在 pending/failed 时阻止 execute
- [x] 3.5 实现备份文件存在性和 SHA256 校验，缺失或不匹配时阻止 execute
- [x] 3.6 实现确认 token 机制，缺失或错误时返回 `MYSQL_CLEANUP_CONFIRMATION_REQUIRED`
- [x] 3.7 为 `conversation_messages` 实现引用检查；仍有外键依赖时禁止全量删除
- [x] 3.8 为 `conversation_messages` 实现大字段瘦身策略，保留稳定 ID 和必要引用字段
- [x] 3.9 确保清理报告和日志不输出明文连接串、API key 或大文本正文

## 4. 测试覆盖

- [x] 4.1 添加 plan 测试，覆盖候选表、禁止表、blocked 状态和通过状态
- [x] 4.2 添加 backup 测试，覆盖文件生成、行数、SHA256 和 Git 忽略路径
- [x] 4.3 添加 dry-run 测试，验证不执行 DELETE/UPDATE
- [x] 4.4 添加 execute 防误删测试，覆盖缺少备份、缺少 token、backend 非 mongo、verify 失败和补偿积压
- [x] 4.5 添加分批清理测试，覆盖成功进度、失败停止和审计报告
- [x] 4.6 添加 `conversation_messages` 引用保护和大字段瘦身测试
- [x] 4.7 添加 post-verify 测试，覆盖 Mongo 完整、MySQL 行数符合策略和失败报告
- [x] 4.8 添加 rollback-import 测试，覆盖恢复、重复主键跳过和冲突统计

## 5. 文档与 Runbook

- [x] 5.1 更新 `docs/database/mongodb-document-storage.md`，加入 `mysql-cleanup` 生命周期阶段
- [x] 5.2 更新 `docs/database/mongodb-migration-runbook.md`，加入 plan、backup、dry-run、execute、post-verify 和 rollback-import 命令
- [x] 5.3 新增或更新清库执行 runbook，明确候选范围、禁止范围、顺序、窗口、备份保留和回滚步骤
- [x] 5.4 记录 `conversation_messages` 默认瘦身而非删除行的原因和后续 drop 表前置条件
- [x] 5.5 明确不修改 `backend/config.yaml` 真实密钥，不提交备份文件和清理报告中的敏感内容

## 6. 验证与执行准备

- [x] 6.1 运行 `ruff check` 和本次新增/修改测试
- [x] 6.2 运行 `bash scripts/check-complexity-budget.sh`
- [x] 6.3 运行 `openspec validate cleanup-mysql-after-mongodb-document-store --type change --strict`
- [x] 6.4 在开发库执行 plan、backup、dry-run 和 rollback-import 演练
- [x] 6.5 输出生产执行 checklist，等待人工确认后才允许 execute
