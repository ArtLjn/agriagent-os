## Purpose

定义 admin-user-api 能力的行为要求。

# Admin 用户管理 API

## 概述
为管理端提供用户 CRUD 和管理接口，仅限 admin 角色访问。

## 接口清单

### GET /admin/users
查询用户列表（分页、筛选）。

**Query 参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | integer | 否 | 页码，默认 1 |
| size | integer | 否 | 每页条数，默认 20，最大 100 |
| status | string | 否 | 按状态筛选：active/disabled |
| phone_keyword | string | 否 | 手机号模糊搜索 |

**响应：**
```json
{
  "items": [
    {
      "id": "uuid",
      "phone": "13800138000",
      "nickname": "农友",
      "avatar_url": null,
      "role": "user",
      "status": "active",
      "created_at": "2026-05-27T10:00:00Z",
      "farm_name": "农友的农场"
    }
  ],
  "total": 100
}
```

### GET /admin/users/{user_id}
获取用户详情。

**Path 参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 UUID |

**响应：** 同列表项 + `farm_id`, `farm_location`

### PUT /admin/users/{user_id}/status
修改用户状态（禁用/启用）。

**Path 参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| user_id | string | 用户 UUID |

**请求体：**
```json
{
  "status": "disabled"
}
```

**响应：**
```json
{
  "id": "uuid",
  "status": "disabled",
  "updated_at": "2026-05-27T12:00:00Z"
}
```

## 权限
所有接口必须携带 `Authorization: Bearer <admin_token>`，且 token 对应的用户 `role == "admin"`，否则返回 403。

## 安全
- 绝不返回 `password_hash` 字段
- 状态修改接口需记录操作日志（后续迭代）
## Requirements
### Requirement: 用户配额查询
系统 SHALL 提供管理员 API 查询单个用户的配额详情。

#### Scenario: GET /admin/users/{user_id}/quota
- **WHEN** 管理员请求用户配额
- **THEN** 返回包含 monthly_limit、monthly_usage、monthly_remaining、monthly_start、monthly_end、weekly_limit、weekly_usage、weekly_remaining、weekly_start、weekly_end、status（normal/warning/exceeded）

#### Scenario: 非管理员禁止查询
- **WHEN** 非管理员请求用户配额接口
- **THEN** 系统 SHALL 返回 403

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

### Requirement: Token 统计接口筛选
系统 SHALL 提供管理员 Token 统计接口，支持 user_id 和 farm_id 过滤；未提供过滤条件时返回全量聚合。

#### Scenario: 按用户筛选 token 汇总
- **WHEN** 管理员请求 GET /admin/stats/tokens?user_id=u1&days=7
- **THEN** 返回该用户近 7 天的 token 汇总

#### Scenario: 按用户和农场交集筛选
- **WHEN** 管理员请求 GET /admin/stats/tokens?user_id=u1&farm_id=2
- **THEN** 返回同时匹配 user_id 和 farm_id 的 token 汇总

#### Scenario: 全量聚合
- **WHEN** 管理员请求 GET /admin/stats/tokens 且未提供 user_id 和 farm_id
- **THEN** 返回所有用户和农场的 token 汇总

#### Scenario: 非管理员禁止查看 token 统计
- **WHEN** 非管理员请求 /admin/stats/tokens 或 /admin/stats/tokens/daily
- **THEN** 系统 SHALL 返回 403

