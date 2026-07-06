## Why

MongoDB 文档存储第 1 期和第 2 期已经覆盖高 JSON 密度对象、在线会话消息、Agent 输出记录和 Guardrails 日志。下一步需要让 MySQL 从“大文本与文档归档库”退回到关系元数据和回滚控制面，降低备份体积、表扫描成本和长期维护噪音。

## What Changes

- 新增三期 MySQL 清库流程：在对象已进入 `mongo` 主模式、Mongo 校验通过、反向同步预览无冲突、备份完成后，按对象清理 MySQL 文档型数据行。
- 清理范围限定为已迁移且 Mongo 可作为 source of truth 的文档表数据；默认保留表结构、外键兼容和最小关系骨架，不做无保护的 `DROP TABLE`。
- `conversation_messages`、`agent_records`、`guardrails_logs` 进入候选清理范围；第 1 期五类文档表进入候选清理范围；`conversations`、`agent_turns`、`feedback_records`、`token_daily_stats`、`agent_data_flywheel_labels` 不进入三期清理。
- 新增清理脚本或扩展迁移脚本，支持 `plan`、`backup`、`verify`、`cleanup --dry-run`、`cleanup --execute`、`post-verify` 和 `rollback-import`。
- 所有清理命令默认 dry-run；真正删除数据必须显式传入 `--execute`、目标表名、备份文件路径和人工确认 token。
- 清理前后产出审计报告，记录 MySQL 行数、Mongo 文档数、备份校验和、删除行数、执行人、执行时间和回滚入口。
- 更新运行文档，给出按对象分批清理顺序、保留策略、回滚步骤和禁止项。
- 不提交生产密钥，不修改 `backend/config.yaml` 中真实连接串或 API key。

## Capabilities

### New Capabilities

- `mysql-document-store-cleanup`: MongoDB 文档存储三期清库能力，定义可清理对象、不可清理对象、执行前置条件、备份、删除、审计和回滚契约。

### Modified Capabilities

- `database-migration-tooling`: 扩展迁移工具，从回填/校验/反向同步扩展到清库 dry-run、备份、执行、后置校验和回滚导入。
- `mongodb-document-storage`: 更新文档存储生命周期，从 `mysql -> dual -> mongo-read -> mongo` 增加 `mysql-cleanup` 阶段，并明确清理后 MySQL 不再作为已清理对象的回滚基准。

## Impact

- **数据库**: 影响第 1 期五张文档表和第 2 期三张文档表的数据保留策略；默认不删除表结构，不删除 `conversations` 和 `agent_turns` 等关系/热路径表。
- **后端代码**: 影响 `backend/scripts/migrate_mysql_to_mongo.py` 或新增清理脚本、Mongo 校验工具、Repository 运行模式检查和文档。
- **运维**: 清理前必须完成数据库备份、Mongo 一致性校验、配置切到 `mongo` 主模式、补偿队列清零和人工审批。
- **测试**: 需要覆盖 dry-run 不删除、execute 需要确认、备份文件生成、清理后校验、回滚导入和禁止清理表保护。
- **安全**: 清理报告必须脱敏连接串和密钥；不得提交 `backend/config.yaml` 真实运行密钥。
