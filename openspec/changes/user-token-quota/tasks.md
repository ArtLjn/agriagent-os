## 1. 数据模型变更

- [ ] 1.1 User 模型新增 token_monthly_limit 和 token_weekly_limit 两个 nullable Integer 列
- [ ] 1.2 TokenDailyStats 模型新增 user_id (String(36), nullable, indexed) 列，更新唯一约束为 (user_id, date, model, call_type)
- [ ] 1.3 TokenQuotaConfig 新增 monthly_limit=3000000 和 weekly_limit=750000，over_quota_action 默认改为 "reject"
- [ ] 1.4 编写数据库迁移脚本：ALTER TABLE 添加新列 + 通过 JOIN farms 回填 token_daily_stats.user_id

## 2. 配额服务重写

- [ ] 2.1 实现 _get_month_range() 和 _get_week_range() 周期日期计算辅助函数
- [ ] 2.2 实现 get_user_quota_limits(user_id, db)：查用户自定义限额，NULL 回退全局默认
- [ ] 2.3 实现 get_period_usage(user_id, period, db)：按 user_id + 日期范围查 SUM(total_tokens)
- [ ] 2.4 实现 QuotaCheckResult dataclass 和 check_user_quota(user_id, db)：月/周双检查
- [ ] 2.5 保留 check_quota(farm_id) 作为向后兼容包装器（查 Farm.user_id 委托 check_user_quota）

## 3. 数据流改造（user_id 透传）

- [ ] 3.1 TraceInfo dataclass 新增 user_id 字段
- [ ] 3.2 TraceDAO.accumulate_token_stats() 新增 user_id 参数，UPSERT 包含 user_id
- [ ] 3.3 TraceCollector.record() 中调用 accumulate_token_stats 时传入 trace.user_id
- [ ] 3.4 init_trace() 调用点解析 user_id（通过 farm_id 查 Farm.user_id）
- [ ] 3.5 graph.py _get_farm_context() 返回值扩展，增加 user_id
- [ ] 3.6 graph.py chat_node 配额检查改为 check_user_quota(user_id)，超限消息周期感知

## 4. 后端 API

- [ ] 4.1 admin_stats.py GET /admin/stats/tokens 新增可选 user_id 过滤参数
- [ ] 4.2 admin_stats.py GET /admin/stats/tokens/daily 新增可选 user_id 过滤参数
- [ ] 4.3 schemas/admin_user.py 新增 UserQuotaStatus、UpdateUserQuotaRequest、UserQuotaOverviewItem
- [ ] 4.4 admin_users.py 新增 GET /admin/users/{user_id}/quota 端点
- [ ] 4.5 admin_users.py 新增 PUT /admin/users/{user_id}/quota 端点
- [ ] 4.6 admin_users.py 新增 GET /admin/users/quota-overview 端点（分页、status 筛选）

## 5. 前端改造

- [ ] 5.1 api/users.ts 新增 getUserQuota、updateUserQuota、getQuotaOverview 函数和类型定义
- [ ] 5.2 api/admin.ts 新增 getUserTokenUsage 函数
- [ ] 5.3 TokenDashboard 新增用户选择器（Select 下拉），API 请求添加 user_id 参数
- [ ] 5.4 TokenDashboard 替换硬编码 QUOTA_LIMIT=10000，改为展示月/周配额进度条
- [ ] 5.5 Users 页面表格新增月用量/月限额和周用量/周限额列（带进度条）
- [ ] 5.6 Users 详情弹窗新增 Token 配额区块（展示 + InputNumber 编辑）
- [ ] 5.7 Users 页面列表加载时并行请求 quota-overview 数据

## 6. 测试

- [ ] 6.1 编写 quota_service 测试：周期计算、用户限额回退、月/周检查、超限拒绝
- [ ] 6.2 编写 admin_user_quota API 测试：查询、修改、概览端点
- [ ] 6.3 更新 admin_stats API 测试：user_id 过滤参数
- [ ] 6.4 运行全量测试确保无回归
