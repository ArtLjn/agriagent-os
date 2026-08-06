# Schema Hardening 迁移说明

## 目标

本迁移用于强化 MySQL schema 的外键、索引、JSON/日期类型和账务分类引用。迁移保持现有 API 兼容，不删除旧 `cost_records.category` 字段。

## 执行前

1. 备份数据库：

```bash
mysqldump -h <host> -u <user> -p --single-transaction --routines --triggers farm_manager > backup.sql
```

2. 运行迁移前审计：

```bash
cd backend
.venv/bin/python -m app.ops.schema_hardening_audit --phase pre --pretty
```

如果报告中存在悬挂引用、非法 JSON 或无法匹配分类，需要先修复或确认处理策略。

## 执行迁移

```bash
cd backend
.venv/bin/alembic upgrade head
```

本阶段迁移会：

- 为 `cost_records` 增加 `category_id` 和 `category_name_snapshot`
- 回填可匹配的账务分类
- 增加核心查询复合索引
- 补充关键外键
- 将 Trace、仿真 JSON、Token 日期和阶段布尔字段映射为更准确类型

## 执行后

运行迁移后校验：

```bash
cd backend
.venv/bin/python -m app.ops.schema_hardening_audit --phase post --pretty
```

期望输出：

```json
{
  "ok": true,
  "total_issue_count": 0
}
```

## 回滚

```bash
cd backend
.venv/bin/alembic downgrade c6f4d9a2e8b1
```

回滚会移除本阶段新增索引、外键和分类关联列，并将类型恢复到迁移前形态。旧 `category` 字段在本阶段始终保留，可用于兼容读取。

## 已知注意事项

- SQLite 测试库不支持完整 MySQL 外键和 JSON 类型变更语义，生产校验以 MySQL 上的 `--phase post` 结果为准。
- `cost_records.category` 暂不删除，后续确认移动端和 Agent 均切到 `category_id` 后再规划清理。
- 如果新增账务分类不存在，服务层会保留旧分类字符串和快照，迁移前审计会报告无法匹配项。
