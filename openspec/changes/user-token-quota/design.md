## Context

当前 token 统计系统按 farm_id 聚合，配额以全局日限额控制（100k/天）。系统已具备：
- `TokenDailyStats` 模型按 (farm_id, date, model, call_type) 聚合
- `quota_service.py` 实现日限额检查
- `graph.py` 在 LLM 调用前拦截超限请求
- Admin Token Dashboard 展示汇总统计

需要扩展为：用户级统计 + 月/周双周期配额 + 超限拒绝 + VIP 差异化基础设施。

## Goals / Non-Goals

**Goals:**
- Token 统计细化到用户维度（user_id）
- 支持月限额 + 周限额双周期检查
- 超限时直接拒绝，Agent 返回周期感知提示
- 全局默认限额，User 模型支持按用户自定义（VIP 预留）
- 管理员可查看/编辑每个用户的配额
- 前端展示月/周配额进度

**Non-Goals:**
- VIP 付费系统（仅预留配额字段，不实现计费流程）
- Token 用量通知/告警机制
- 按模型差异化计费
- 实时 WebSocket 配额推送

## Decisions

### 1. user_id 加到 TokenDailyStats 而非新建表

**选择**: 在现有 `TokenDailyStats` 表新增 `user_id` 列。

**替代方案**: 创建独立 `UserTokenStats` 表。
**理由**: 单一数据源避免双写和数据不一致。TokenDailyStats 已是聚合层，直接加 user_id 即可按用户查询。

### 2. 周期范围纯计算，不存储周期记录

**选择**: `_get_month_range()` / `_get_week_range()` 纯函数计算日期范围，SQL `BETWEEN` 过滤。

**替代方案**: 创建 quota_periods 表存储每个周期的起止时间。
**理由**: 无额外表、无定时任务重置周期。日期是确定性的，纯计算更简单可靠。

### 3. 配额字段放 User 模型

**选择**: User 表新增 `token_monthly_limit` / `token_weekly_limit` 两个 nullable Integer 列。NULL = 使用全局默认。

**替代方案**: 独立 UserQuota 表。
**理由**: 仅两列，独立表增加 JOIN 开销和维护成本。未来如果配额维度增多再考虑拆分。

### 4. check_quota(farm_id) 保留为向后兼容包装器

**选择**: 旧接口内部查 Farm.user_id 后委托 `check_user_quota(user_id)`。

**理由**: graph.py 等调用点改动最小，渐进式迁移。

### 5. TraceInfo 直接携带 user_id

**选择**: 在 init_trace 阶段解析 user_id 并存入 TraceInfo，后续透传。

**替代方案**: 在 accumulate_token_stats 中从 farm_id 反查。
**理由**: user_id 只解析一次，避免每次 token 写入时额外查库。

## Risks / Trade-offs

- **[数据库迁移]** TokenDailyStats 已有数据的 user_id 为 NULL → 迁移时通过 JOIN farms 回填，新数据从 init_trace 获取。
- **[唯一约束变更]** 从 (farm_id, date, model, call_type) 改为 (user_id, date, model, call_type) → 需要重建约束，旧数据中 user_id 回填后约束一致。
- **[并发写入]** UPSERT 无锁在高并发下可能丢失计数 → 当前用户量小可接受，后续可加悲观锁或 INSERT ON CONFLICT。
- **[前端 QUOTA_LIMIT 不一致]** 当前前端硬编码 10000，后端 100000 → 改为从后端 API 获取实际配额值。
