## Why

后端 `storage-redesign-multi-user` 已完成了多用户认证基础设施（users 表、JWT、auth API），但：

1. **FarmManagerMobile（App）完全没有接入认证系统** — 当前所有请求无认证头，直接以匿名方式访问 API，一旦后端开启认证校验，App 将完全不可用
2. **admin-web 缺少用户管理功能** — 作为系统管理后台，无法查看注册用户列表、用户详情、禁用异常账号，运维盲区
3. **后端缺少 admin 用户管理 API** — 当前 admin.py 只有 guardrails-logs，没有用户 CRUD 和管理接口

这是一个"基础设施已就绪，前端/管理端缺失"的补齐型变更。

## What Changes

- **后端新增 Admin 用户管理 API**：用户列表（分页/筛选）、用户详情、禁用/启用用户、用户统计
- **admin-web 新增用户管理页面**：用户列表页（表格展示、状态筛选、分页）、用户详情弹窗、禁用/启用操作
- **FarmManagerMobile 接入认证系统**：登录页、注册页、个人中心页、请求自动携带 JWT token、token 过期处理
- **接口同步**：两端共用同一套后端 admin API，Schema 保持一致

## Capabilities

### New Capabilities
- `admin-user-api`: 后端 admin 用户管理接口（列表、详情、状态管理、统计）
- `admin-web-user-management`: 管理端用户管理页面（列表、详情、操作）
- `app-auth-integration`: App 端认证接入（登录/注册/个人中心/token 管理）

### Modified Capabilities
- 无（基础设施已在 storage-redesign-multi-user 中完成）

## Impact

- **后端**：新增 `app/api/admin_users.py` 路由模块，新增 admin 用户相关 schemas
- **admin-web**：新增 `pages/Users/` 目录，新增 `api/users.ts` 接口模块，更新 `AdminLayout` 导航菜单
- **FarmManagerMobile**：新增 `screens/auth/` 目录（LoginScreen、RegisterScreen、ProfileScreen），修改 `api/client.ts` 注入 token，新增 `stores/authStore.ts`
- **数据库**：无变更（复用现有 users 表）
- **测试**：后端 admin API 测试、admin-web 页面测试、App 端 E2E 测试
