## 1. 迁移前审计

- [ ] 1.1 编写 schema hardening 迁移前检查命令，扫描悬挂用户、农场、会话、分类、作物周期引用
- [ ] 1.2 增加 JSON 字段合法性扫描，覆盖 trace、agent record、conversation message、simulation 相关结构化字段
- [ ] 1.3 增加账务分类匹配报告，按 `farm_id + category + record_type` 检测无法匹配的 `cost_records`
- [ ] 1.4 在测试中覆盖迁移前检查命令的通过、失败和报告输出场景

## 2. ORM 与 Alembic Schema 变更

- [ ] 2.1 更新 SQLAlchemy models，增加缺失外键、删除策略和关系字段
- [ ] 2.2 为 `cost_records` 增加 `category_id` 和 `category_name_snapshot` 字段，并保持旧 `category` 字段兼容
- [ ] 2.3 将明确结构化字段迁移为 MySQL JSON 类型，并调整对应 ORM 类型
- [ ] 2.4 将 `token_daily_stats.date`、`trace_records.start_time/end_time`、`cycle_stages.is_current` 调整为准确类型
- [ ] 2.5 增加核心查询复合索引并删除主键冗余二级索引
- [ ] 2.6 生成分阶段 Alembic migration，并为每个阶段提供 downgrade

## 3. 数据回填与兼容适配

- [ ] 3.1 实现 `cost_records.category_id` 回填逻辑，支持匹配已有分类并写入分类名称快照
- [ ] 3.2 为无法匹配分类的账务记录提供报告和可配置处理策略
- [ ] 3.3 调整 `cost_service`、`debt_service`、成本解析和相关 schemas，优先使用 `category_id`，保留旧字段读取兼容
- [ ] 3.4 调整 trace、token 统计、仿真写入逻辑，确保 JSON 和时间类型写入合法

## 4. 迁移后校验

- [ ] 4.1 编写迁移后校验命令，验证关键外键、复合索引、JSON 类型和核心表行数
- [ ] 4.2 增加账务、分类、会话、trace、token 统计的数据库集成测试
- [ ] 4.3 运行 Alembic upgrade/downgrade 冒烟测试，确认迁移可前进和回滚
- [ ] 4.4 运行后端测试、ruff 检查和架构约束检查，记录已知非本变更问题

## 5. 文档与发布

- [ ] 5.1 更新数据库架构文档，说明新增外键、索引、JSON 类型和成本分类迁移策略
- [ ] 5.2 更新运维迁移说明，包含备份、检查、执行、验证和回滚步骤
- [ ] 5.3 更新 `backend/sql/farm_manager.sql` 或导出流程，确保 schema dump 与 Alembic head 一致
