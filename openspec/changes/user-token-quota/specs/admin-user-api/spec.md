## ADDED Requirements

### Requirement: 用户配额查询
系统 SHALL 提供管理员 API 查询单个用户的配额详情。

#### Scenario: GET /admin/users/{user_id}/quota
- **WHEN** 管理员请求用户配额
- **THEN** 返回包含 monthly_limit、monthly_usage、monthly_remaining、monthly_start、monthly_end、weekly_limit、weekly_usage、weekly_remaining、weekly_start、weekly_end、status（normal/warning/exceeded）

### Requirement: 用户配额修改
系统 SHALL 提供管理员 API 修改单个用户的 token 配额。

#### Scenario: PUT /admin/users/{user_id}/quota
- **WHEN** 管理员发送 {"token_monthly_limit": 5000000, "token_weekly_limit": 1200000}
- **THEN** 用户对应的配额字段更新，返回更新后的配额状态

#### Scenario: 配额设为 null 恢复默认
- **WHEN** 管理员发送 {"token_monthly_limit": null}
- **THEN** 用户 token_monthly_limit 字段清空，回退使用全局默认值

### Requirement: 全量用户配额概览
系统 SHALL 提供管理员 API 查询所有用户的配额概览，支持分页。

#### Scenario: GET /admin/users/quota-overview
- **WHEN** 管理员请求配额概览（page=1, size=20）
- **THEN** 返回分页列表，每项包含 user_id、nickname、phone、monthly_limit、monthly_usage、monthly_percent、weekly_limit、weekly_usage、weekly_percent、status

#### Scenario: 筛选超限用户
- **WHEN** 管理员请求 quota-overview?status=exceeded
- **THEN** 仅返回配额已超限的用户
