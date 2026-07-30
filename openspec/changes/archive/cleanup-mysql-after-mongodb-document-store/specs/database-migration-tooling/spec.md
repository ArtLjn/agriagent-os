## ADDED Requirements

### Requirement: MySQL 文档表清理计划
迁移工具 SHALL 支持生成 MySQL 文档表清理计划，展示每张候选表是否满足三期清库条件。

#### Scenario: 输出清理计划
- **WHEN** 开发者运行清理计划命令
- **THEN** 工具输出候选表、MySQL 行数、Mongo 文档数、storage backend、最近 verify 状态、补偿队列状态和清理建议
- **AND** 工具不得修改 MySQL 或 Mongo 数据

#### Scenario: 计划标记 blocked
- **WHEN** 候选表缺少 Mongo 校验、backend 未切到 `mongo` 或存在补偿积压
- **THEN** 工具必须将该表标记为 `blocked`
- **AND** 工具必须输出阻塞原因和下一步命令建议

### Requirement: MySQL 文档表备份
迁移工具 SHALL 在真实清理前导出目标表备份，并生成可校验的 SHA256 摘要。

#### Scenario: 生成 JSONL 备份
- **WHEN** 开发者运行目标表备份命令
- **THEN** 工具按主键升序导出 MySQL 行到 JSONL 或 SQL dump
- **AND** 工具生成包含行数、文件路径和 SHA256 的备份元数据

#### Scenario: 备份目录防入库
- **WHEN** 工具生成备份文件
- **THEN** 默认输出目录必须位于 Git 忽略路径或显式外部路径
- **AND** 工具不得将备份内容写入项目根目录临时文件

### Requirement: MySQL 文档表清理执行
迁移工具 SHALL 支持分批 dry-run 和显式 execute 清理，且 execute 必须具备防误删保护。

#### Scenario: dry-run 预览批次
- **WHEN** 开发者运行清理 dry-run
- **THEN** 工具输出预计删除或瘦身的行数、批次数、每批大小和预计影响
- **AND** 工具不得执行 `DELETE` 或 `UPDATE`

#### Scenario: 分批执行清理
- **WHEN** 开发者运行带确认 token 的 execute 清理
- **THEN** 工具按主键范围分批执行
- **AND** 每批提交后记录进度、删除数量、耗时和错误上下文

#### Scenario: 清理失败停止
- **WHEN** 任一批次删除或瘦身失败
- **THEN** 工具必须停止后续批次
- **AND** 工具必须输出可用于继续或回滚的审计状态

### Requirement: 清理后校验与回滚导入
迁移工具 SHALL 支持清理后的 post-verify 和从备份 rollback-import。

#### Scenario: 清理后校验 Mongo 完整性
- **WHEN** 清理 execute 完成
- **THEN** 工具必须验证 Mongo 文档数和关键字段仍满足清理前校验报告
- **AND** 工具必须验证 MySQL 行数符合目标清理策略

#### Scenario: 回滚导入备份
- **WHEN** 开发者运行 rollback-import
- **THEN** 工具从备份文件恢复目标表 MySQL 数据
- **AND** 工具必须避免重复插入已存在主键
- **AND** 工具必须输出恢复行数和冲突行数
