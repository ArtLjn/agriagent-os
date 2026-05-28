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
