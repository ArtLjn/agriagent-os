## Why

当前 token 统计和配额仅按 farm_id 维度，使用全局统一限额（100k/天）。无法细化到每个用户的用量，也无法按月/周周期控制配额。需要支持用户级 token 统计和限额，为后续 VIP 差异化服务提供基础。

## What Changes

- TokenDailyStats 新增 user_id 列，统计细化到用户维度
- User 模型新增 token_monthly_limit / token_weekly_limit 字段（NULL 表示用全局默认）
- 配额检查从全局日限额改为按用户的月限额 + 周限额双周期检查
- 超限策略改为直接拒绝（Agent 返回提示消息，不调用 LLM）
- 新增管理员 API：查询/修改用户配额、全量用户配额概览
- 前端 Token 看板支持按用户筛选
- 前端用户管理页展示月/周配额进度条，支持编辑用户限额
- 修复前端 QUOTA_LIMIT=10000 与后端 daily_limit=100000 不一致的问题

## Capabilities

### New Capabilities
- `user-token-quota`: 用户级 token 配额系统 — 月/周周期限额、超限拒绝、管理员可按用户自定义限额

### Modified Capabilities
- `token-dashboard-ui`: 新增用户筛选器，展示月/周配额进度条替代硬编码的日配额
- `admin-user-api`: 新增配额查询/修改/概览端点
- `admin-web-user-management`: 用户表格新增配额列，详情弹窗新增配额编辑区

## Impact

- **数据模型**: User 表新增 2 列，TokenDailyStats 表新增 user_id 列 + 更新唯一约束
- **后端服务**: quota_service.py 完整重写，trace_collector/trace_dao 透传 user_id
- **Agent**: graph.py 配额检查点从 check_quota(farm_id) 改为 check_user_quota(user_id)
- **API**: admin_stats 和 admin_users 路由扩展
- **前端**: TokenDashboard 和 Users 页面改造
- **数据库迁移**: 需要 ALTER TABLE + 回填 user_id
