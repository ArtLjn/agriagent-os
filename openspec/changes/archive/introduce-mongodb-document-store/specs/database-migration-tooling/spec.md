## ADDED Requirements

### Requirement: MySQL 到 MongoDB 幂等回填
系统 SHALL 提供可重复执行的 MySQL 到 MongoDB 回填脚本，支持第 1 期五张目标表。

#### Scenario: 分批回填目标表
- **WHEN** 开发者运行 MySQL 到 MongoDB 回填脚本并指定目标表与 batch size
- **THEN** 脚本按 MySQL 自增主键升序分批读取数据
- **AND** 脚本将每行转换为 Mongo 文档并写入对应集合
- **AND** 脚本输出已扫描、已写入、已跳过和失败数量

#### Scenario: 重复执行回填
- **WHEN** 回填脚本遇到 MongoDB 中已存在相同 `mysqlId` 的文档
- **THEN** 脚本跳过或幂等更新该文档
- **AND** 脚本不得创建重复业务文档

#### Scenario: 回填失败批次
- **WHEN** 单个批次写入 MongoDB 失败
- **THEN** 脚本重试该批次并记录失败上下文
- **AND** 超过重试次数后脚本记录失败批次的 ID 范围，便于后续补偿重放

### Requirement: MySQL 与 MongoDB 一致性校验
系统 SHALL 提供数据一致性校验脚本，在切读 MongoDB 前验证行数、缺失 ID 和关键字段。

#### Scenario: 行数与缺失 ID 校验
- **WHEN** 开发者运行一致性校验脚本
- **THEN** 脚本对比 MySQL 目标表行数与 MongoDB 目标集合文档数
- **AND** 脚本输出 MongoDB 缺失的 `mysqlId` 列表或摘要

#### Scenario: 关键字段抽样校验
- **WHEN** 校验脚本抽样比对目标对象
- **THEN** 脚本验证 MySQL 行与 Mongo 文档的业务 ID、`farmId`、状态字段和关键 JSON 字段一致
- **AND** 脚本对 JSON 字段进行规范化后再比较，避免字段顺序导致误报

#### Scenario: 校验阈值阻止切读
- **WHEN** 不一致率超过配置阈值
- **THEN** 校验脚本返回非零退出码
- **AND** 系统不得自动切换到 `mongo-read` 或 `mongo` 模式

### Requirement: 双写补偿重放工具
系统 SHALL 提供补偿重放工具，用于处理双写期 MongoDB 写失败的对象。

#### Scenario: 重放待补偿对象
- **WHEN** 开发者运行补偿重放命令
- **THEN** 工具读取待补偿任务并从 MySQL 重新加载对应对象
- **AND** 工具将对象幂等写入 MongoDB
- **AND** 成功后标记补偿任务完成

#### Scenario: 补偿对象已不存在
- **WHEN** 补偿重放时 MySQL 中找不到对应对象
- **THEN** 工具标记该任务为失败并记录 `not_found` 原因
- **AND** 工具不得创建缺少 source of truth 的 Mongo 文档

### Requirement: Mongo 到 MySQL 反向同步预案
系统 SHALL 为进入 Mongo 主模式后的紧急回滚提供 Mongo 到 MySQL 的反向同步脚本入口。

#### Scenario: 反向同步增量文档
- **WHEN** 运维需要从 `mongo` 模式回滚到 MySQL
- **THEN** 反向同步脚本按 `mysqlId` 和更新时间扫描 Mongo 文档
- **AND** 脚本将 MySQL 缺失或落后的记录补齐
- **AND** 脚本输出需要人工复核的冲突记录

#### Scenario: 反向同步冲突
- **WHEN** Mongo 文档与 MySQL 行同时存在且关键字段冲突
- **THEN** 脚本不得静默覆盖 MySQL 数据
- **AND** 脚本记录冲突详情并要求人工确认处理
