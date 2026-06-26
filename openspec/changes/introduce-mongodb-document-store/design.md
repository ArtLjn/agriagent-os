## Context

当前 Farm Manager 已经以 MySQL 承载核心事务数据，但 Trace 和 Data Flywheel 中存在多张高 JSON 密度表：

- `trace_records`: `input_data`、`output_data`、`token_usage` 等 JSON 字段持续追加，且被 admin trace、discovery rule、issue chain evidence 等路径读取。
- `agent_case_drafts`、`agent_repair_packs`、`agent_review_issue_chains`、`agent_data_flywheel_prelabels`: 字段本质是评测、预标注、修复包和问题链文档，schema 随数据飞轮迭代高频变化。

本设计落实 `farm-manager-design-spec/01_正式设计/14_MongoDB迁移方案.md` 第 1 期。生产切换必须保持 MySQL 可回滚，所有新增代码遵守现有模块边界：基础设施在 `app/infra` 或 `app/core`，Data Flywheel 在 `app/modules/data_flywheel`，Trace 写入继续从 `TraceDAO`/TraceCollector 入口收敛。

## Goals / Non-Goals

**Goals:**

- 为第 1 期五类对象引入 MongoDB 文档存储，减轻 MySQL JSON、大文本和 schema 演进压力。
- 建立统一 Mongo client、配置、健康检查、集合索引初始化和多租户 `farmId` 查询约束。
- 为每类对象提供 MySQL Repository、Mongo Repository、DualWrite Repository 和映射器，服务层通过接口访问存储。
- 支持 `mysql -> dual -> mongo-read -> mongo` 的渐进切换，并在双写和切读阶段提供回退。
- 提供幂等历史回填、数据校验、补偿重放和反向同步脚本入口。
- 将 Mongo 写失败、读回退、校验不一致和切换阈值纳入结构化日志与运维 runbook。

**Non-Goals:**

- 不迁移 `conversations`、`conversation_messages`、`agent_records`、`guardrails_logs` 或 `agent_turns.rule_hits`。
- 不删除 MySQL 表，不在本变更中关闭 MySQL 写入。
- 不改动用户侧或 admin-web 的 API contract；返回字段保持兼容。
- 不引入 Kafka、CDC、ClickHouse、数据湖或复杂跨库事务。
- 不把 MongoDB 作为强事务 source of truth；第 1 期 MySQL 仍是回滚基准。

## Decisions

### 1. 存储切换模式：Repository + 配置驱动

**选择**: 为每类对象定义 Repository Protocol，并提供 `mysql`、`dual`、`mongo-read`、`mongo` 四种模式。

**替代方案**:

- 在现有 SQLAlchemy 查询旁边直接插 Mongo 调用：改动快，但直写点难以审计，无法统一回滚和指标。
- 一次性全量切 Mongo：代码少，但生产风险大，且缺少回退窗口。

**理由**: Repository 能把映射、双写、回退、补偿和 farm 隔离集中起来。配置切换让上线可分阶段推进，也便于在异常时立即切回 MySQL。

### 2. 双写策略：MySQL 先写，Mongo 异步补偿

**选择**: 双写期先提交 MySQL，再写 Mongo；Mongo 写失败只记录结构化日志并写入补偿队列，不影响主流程返回。

**替代方案**:

- Mongo 先写再写 MySQL：会让文档库异常影响现有事务路径。
- 两库强一致事务：跨库事务复杂且不符合当前轻量部署。

**理由**: 第 1 期目标是降低风险而不是追求跨库原子性。MySQL 继续作为 source of truth，补偿重放和一致性校验负责收敛最终一致。

### 3. Mongo 文档模型：保留业务 ID 与扁平索引字段

**选择**: 每个文档保留 `mysqlId`、`farmId`、业务 ID（如 `requestId`、`draftId`、`packId`、`chainId`、`sampleId`）和查询所需顶层字段，复杂 JSON 放入嵌套文档。

**替代方案**:

- 直接原样 dump MySQL 行：实现简单，但无法发挥嵌套字段索引优势。
- 完全脱离 MySQL ID：文档更纯粹，但双写、回填、校验和回滚难度上升。

**理由**: `mysqlId` 是幂等回填和双写防重的关键。`farmId` 与业务 ID 顶层化能保证多租户过滤和常用查询索引命中。

### 4. 集合与索引：第 1 期显式初始化

**选择**: 新增 `scripts/mongo/init_indexes.js` 或等价 Python 初始化脚本，显式创建 `traceRecords`、`caseDrafts`、`repairPacks`、`reviewIssueChains`、`prelabels` 索引。

**关键索引**:

- 所有集合：`{ mysqlId: 1 }` 唯一索引。
- 租户查询：以 `farmId` 作为复合索引前缀。
- 业务定位：Trace 的 `requestId` 是非唯一查询索引，同一请求可包含多条 trace node，唯一性依赖 `{ mysqlId: 1 }`；`draftId`、`packId`、`chainId` 建唯一索引；`prelabels` 使用 `sampleId + source` 组合查询索引。
- Trace TTL：仅 `traceRecords.createdAt` 配置 TTL；飞轮数据默认永久保留。

**理由**: Open-ended 文档 schema 不能等于 open-ended 查询。显式索引能在切读前通过 explain 和测试验证。

### 5. 多租户隔离：Repository 强制 farmId

**选择**: Mongo Repository 的列表、详情和更新方法必须接收 `farm_id`，查询条件必须包含 `farmId`；仅内部迁移脚本允许按 `mysqlId` 批处理。

**替代方案**:

- 依赖调用方传过滤条件：容易漏。
- 按租户拆集合：隔离强，但当前租户规模不需要额外复杂度。

**理由**: 与 MySQL 现有 farm_id 隔离策略保持一致，也让代码审计点集中。

### 6. 迁移方式：批量回填 + 双写增量 + 校验切读

**选择**: 历史数据按 MySQL 自增 ID 分批回填，回填脚本以 `mysqlId` 幂等 upsert；双写打开后承接增量；校验通过后再进入 `mongo-read`。

**替代方案**:

- 停机窗口全量迁移：实现简单，但对生产可用性和回滚不友好。
- CDC 实时同步：一致性更强，但引入新基础设施超出第 1 期。

**理由**: 五张目标表以追加/离线数据为主，批量回填加双写足够支撑第 1 期。

### 7. 代码落点：贴合现有模块

**选择**:

- Mongo client 和健康检查放在 `app/infra/mongo.py` 或 `app/core/mongo.py`。
- Trace 存储接口放在 `app/infra/trace_repository.py`，由 `TraceDAO` 使用。
- Data Flywheel 存储接口放在 `app/modules/data_flywheel/repositories/`。
- 映射器放在对应模块的 `mongo_mapper.py` 或 `mappers.py`。
- 迁移脚本放在 `backend/app/scripts/` 或 `backend/scripts/` 的既有脚本区域。

**理由**: 避免创建横跨业务的“万能 repository”目录，减少边界漂移。

## Risks / Trade-offs

- **[跨库不一致]** MySQL 写成功但 Mongo 写失败。→ 结构化记录 `mongo_secondary_write_failed`，写补偿队列；校验脚本按 `mysqlId` 查缺补漏。
- **[切读后 Mongo 查询失败]** admin trace 或飞轮读取异常。→ `mongo-read` 模式必须回退 MySQL，并记录 `mongo_read_fallback_to_mysql`。
- **[索引遗漏导致慢查询]** 切读后 Mongo CPU 或延迟升高。→ 索引初始化纳入部署前检查，关键查询在测试和灰度使用 explain 验证。
- **[敏感信息进入文档库]** Trace/output/debug evidence 可能含密钥。→ 复用现有脱敏策略；修复包和 trace 写入 Mongo 前保持字段脱敏与截断。
- **[MongoDB 暴露风险]** 连接串和 27017 端口可能被扫描。→ 生产启用强密码、IP 白名单、TLS；连接串只进配置或环境变量，不入库。
- **[资源争用]** 单机 Mongo 与 MySQL 抢内存。→ 第 1 期限制 WiredTiger cache，监控 RSS、连接数和查询延迟。
- **[Repository 改造面大]** 现有服务存在直接 SQLAlchemy 查询。→ 先收敛五张目标表的写路径和主要读路径，任务中加入 `rg` 审计和剩余直查记录。

## Migration Plan

1. **准备配置与连接**: 添加 Mongo 配置、依赖、client lifecycle、健康检查和本地/测试配置示例。
2. **初始化集合索引**: 新增索引脚本并在开发环境验证所有索引存在。
3. **实现映射器与 Repository**: 先覆盖 Trace，再覆盖四类 Data Flywheel 文档；单元测试验证行/文档互转。
4. **接入双写**: 默认配置仍为 `mysql`；逐类开启 `dual`，观察 Mongo 写失败率和补偿队列。
5. **历史回填**: 分表运行回填脚本，按 `id ASC` 批量 upsert，记录进度和失败批次。
6. **一致性校验**: 对比 count、缺失 `mysqlId`、关键字段抽样和 JSON 规范化结果；不一致率必须低于阈值。
7. **切读灰度**: 将低风险管理端读取切到 `mongo-read`，保留 MySQL 回退，观察至少 3 天。
8. **生产读切换**: 按表切换到 `mongo-read`，稳定后再评估 `mongo` 写入模式；第 1 期结束仍保留 MySQL 表。
9. **文档同步**: 更新 MongoDB 迁移方案、数据库结构设计、运维 runbook 和配置说明。

**Rollback**:

- 双写期异常：配置切回 `mysql`，暂停补偿 worker，保留 Mongo 数据用于排查。
- 切读异常：配置从 `mongo-read` 切回 `dual` 或 `mysql`，所有读取回到 MySQL。
- 若已进入 `mongo` 写入模式：运行 Mongo 到 MySQL 反向同步脚本补齐缺口，再切回 `mysql`；该阶段需人工审批。

**Rollback triggers**:

- Mongo 读错误率 5 分钟窗口 > 1%。
- Mongo 写失败率 > 0.1%。
- 主流程 P99 延迟上升 > 50%。
- 一致性校验不一致率 > 0.01%。

## Open Questions

- 第 1 期生产 Mongo 是否立即启用 TLS：建议启用，若证书准备阻塞，必须只允许内网或安全组白名单访问。
- 补偿队列落点使用 MySQL 表、Redis 还是本地文件：建议优先 MySQL 表，便于事务后持久化和 admin 可观测。
- Trace TTL 使用 18 个月还是沿用当前 `trace_ttl_days`：建议 Mongo trace 默认 18 个月，MySQL 清理策略保持独立，最终由运维容量评估确认。
- `mongo` 写入模式是否在第 1 期启用：建议第 1 期只完成双写和切读，关闭 MySQL 写入作为后续单独变更。
