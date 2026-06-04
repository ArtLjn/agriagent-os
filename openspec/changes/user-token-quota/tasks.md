## 1. 数据模型变更

- [x] 1.1 User 模型新增 token_monthly_limit 和 token_weekly_limit 两个 nullable Integer 列
- [x] 1.2 TokenDailyStats 模型新增 user_id (String(36), nullable, indexed) 列，保留 farm_id，更新唯一约束为 (user_id, farm_id, date, model, call_type)
- [x] 1.3 TokenQuotaConfig 新增 monthly_limit=3000000 和 weekly_limit=750000，over_quota_action 统一为 warn/reject 且默认改为 "reject"
- [ ] 1.4 编写数据库迁移脚本：ALTER TABLE 添加新列 + 通过 JOIN farms 回填 token_daily_stats.user_id
- [x] 1.5 更新 config.yaml.example、admin_config 返回结构和前端配置类型，移除 daily_limit 展示依赖

## 2. 配额服务重写

- [x] 2.1 实现 _get_month_range() 和 _get_week_range() 周期日期计算辅助函数
- [x] 2.2 实现 get_user_quota_limits(user_id, db)：查用户自定义限额，NULL 回退全局默认
- [x] 2.3 实现 get_period_usage(user_id, period, db)：按 user_id + 日期范围查 SUM(total_tokens)
- [x] 2.4 实现 QuotaCheckResult dataclass 和 check_user_quota(user_id, db)：返回 allowed、exceeded_period、usage、limit、remaining、reset_at 等结构化信息
- [x] 2.5 保留 check_quota(farm_id) 作为向后兼容包装器（查 Farm.user_id 委托 check_user_quota）
- [x] 2.6 缺失 user_id 或用户不存在时返回拒绝结果，避免匿名 LLM 请求绕过配额

## 3. 数据流改造（user_id 透传）

- [x] 3.1 TraceInfo dataclass 新增 user_id 和 call_type 字段，init_trace 支持显式传入
- [x] 3.2 实现 provider usage 归一化函数：优先读取 AIMessage.usage_metadata，再兼容 response_metadata.token_usage，输出 prompt_tokens/completion_tokens/total_tokens/usage_source
- [x] 3.3 TraceDAO.accumulate_token_stats() 新增 user_id 和 call_type 参数，UPSERT 包含 user_id + farm_id
- [x] 3.4 TraceCollector.record() 中仅在 usage_source 为 provider/usage_metadata 时调用 accumulate_token_stats；缺失 usage 时只记录 trace warning
- [ ] 3.5 流式 LLM 尽量启用 usage 返回；如果 provider 封装不支持，则 trace 标记 missing_stream_usage 且不写 TokenDailyStats
- [x] 3.6 确认 token 统计只有 TraceCollector.record(node_type="llm_call") 一个写入口，避免 API 层或 Agent 层重复累计
- [x] 3.7 chat_with_agent / stream_chat_with_agent 调用 invoke_advisor / stream_advisor 时透传 current_user.id
- [x] 3.8 invoke_advisor / stream_advisor 将 user_id 写入 init_trace 和 LangGraph state
- [x] 3.9 graph.py chat_node 配额检查改为 check_user_quota(user_id)，根据 QuotaCheckResult 返回周期感知超限消息
- [ ] 3.10 daily_advice/report 等非 chat LLM 入口设置准确 call_type，避免所有 token 都落为 chat

## 4. 后端 API

- [x] 4.1 admin_stats.py GET /admin/stats/tokens 新增可选 user_id 和 farm_id 过滤参数；都不传时返回全量聚合
- [x] 4.2 admin_stats.py GET /admin/stats/tokens/daily 新增可选 user_id 和 farm_id 过滤参数；都不传时返回全量聚合
- [x] 4.3 schemas/admin_user.py 新增 UserQuotaStatus、UpdateUserQuotaRequest、UserQuotaOverviewItem
- [x] 4.4 admin_users.py 新增 GET /admin/users/{user_id}/quota 端点
- [x] 4.5 admin_users.py 新增 PUT /admin/users/{user_id}/quota 端点
- [x] 4.6 admin_users.py 新增 GET /admin/users/quota-overview 端点（分页、status 筛选）
- [x] 4.7 admin_stats.py 两个 token 统计端点补齐 require_admin 鉴权

## 5. 前端改造

- [x] 5.1 api/users.ts 新增 getUserQuota、updateUserQuota、getQuotaOverview 函数和类型定义
- [x] 5.2 api/admin.ts 新增 getUserTokenUsage 函数，并更新 AdminConfig.token_quota 类型为 monthly_limit / weekly_limit / over_quota_action
- [x] 5.3 TokenDashboard 新增用户选择器（Select 下拉），API 请求添加 user_id 参数
- [x] 5.4 TokenDashboard 替换硬编码 QUOTA_LIMIT=10000，改为展示月/周配额进度条
- [x] 5.5 Users 页面表格新增月用量/月限额和周用量/周限额列（带进度条）
- [ ] 5.6 Users 详情弹窗新增 Token 配额区块（展示 + InputNumber 编辑）
- [x] 5.7 Users 页面列表加载时并行请求 quota-overview 数据
- [x] 5.8 ConfigKeys 页面将 Token 配额配置从日限额改为月/周默认限额，并将 block 文案统一为 reject

## 6. 测试

- [x] 6.1 编写 quota_service 测试：周期计算、用户限额回退、月/周检查、超限拒绝
- [x] 6.2 编写 usage 归一化测试：usage_metadata、response_metadata.token_usage、缺失 usage、字段缺失归零/拒绝策略
- [x] 6.3 编写 trace/token_stats 测试：user_id、farm_id、call_type 透传，且只有 llm_call 会累计 TokenDailyStats
- [x] 6.4 编写 admin_user_quota API 测试：查询、修改、概览端点
- [x] 6.5 更新 admin_stats API 测试：user_id/farm_id 过滤参数、全量聚合、管理员鉴权
- [ ] 6.6 更新 Agent Runtime 测试：超限 reject 不调用 LLM，warn 继续调用并记录日志
- [ ] 6.7 更新流式调用测试：缺失 usage 时不写 TokenDailyStats 但记录 trace warning
- [ ] 6.8 运行全量测试确保无回归
