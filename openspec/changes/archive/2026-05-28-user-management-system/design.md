## Context

`storage-redesign-multi-user` 已完成后端多用户认证基础设施：

- `users` 表：id(UUID), phone, password_hash, nickname, avatar_url, role, status, created_at
- `farms` 表：user_id 关联 users
- Auth API：`POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `PUT /auth/me`
- JWT 三层依赖链：`get_current_user` → `get_current_farm` → `verify_resource_owner`
- 角色字段：`role` (user/admin)，`status` (active/disabled)

但前端和管理端完全未接入：
- **App**：所有 API 请求无 Authorization header，一旦开启认证即不可用
- **admin-web**：导航菜单只有开发/运维工具，无用户管理入口

## Goals / Non-Goals

**Goals:**
- 后端提供 admin 用户管理 API（列表、详情、状态管理）
- admin-web 实现用户管理页面（列表查看、详情、禁用/启用）
- App 实现登录/注册/个人中心，所有请求自动携带 JWT
- Token 过期后自动跳转登录页

**Non-Goals:**
- 不做短信验证码（已有决策，等营业执照）
- 不做 OAuth 登录（已有决策，表结构预留）
- 不做 RBAC 细粒度权限（当前只有 user/admin 两角色）
- 不做密码重置/找回（后续迭代）
- 不改数据库 schema（复用现有 users 表）

## Decisions

### D1: Admin API 使用独立路由模块

**选择：** 新增 `app/api/admin_users.py`（`GET /admin/users`, `GET /admin/users/{id}`, `PUT /admin/users/{id}/status`），不混在 `admin.py` 中。

**理由：** `admin.py` 当前只有 guardrails-logs，职责清晰。用户管理是独立业务域，单独模块便于维护。统一使用 `require_admin` 依赖校验角色。

### D2: Admin API 返回字段控制

**选择：** 用户列表和详情接口**不返回** `password_hash`。返回字段：id, phone, nickname, avatar_url, role, status, created_at, farm_name（JOIN farms 表获取）。

**理由：** 密码哈希属于敏感信息，任何场景都不应返回给客户端。

### D3: App 端 token 存储策略

**选择：** React Native 使用 `expo-secure-store`（iOS Keychain / Android Keystore）存储 JWT token，退出登录时清除。

**备选方案：**
- AsyncStorage → 明文存储，不安全
- 内存存储 → 应用重启后丢失

**理由：** SecureStore 是 RN 官方推荐的安全存储方案，与系统级密钥库集成。

### D4: App 端 token 过期处理

**选择：** API 请求收到 401 时，清除本地 token 并强制跳转登录页。token 有效期 7 天（与后端一致），暂不做 refresh token。

**理由：** 最小实现。refresh token 机制需要额外接口和存储，后续迭代添加。

### D5: App 登录态持久化

**选择：** App 启动时从 SecureStore 读取 token，调用 `GET /auth/me` 验证有效性。有效则进入主界面，无效则跳转登录页。

**理由：** 避免每次启动都让用户重新登录，同时确保 token 未过期/未禁用。

### D6: Admin-web 用户列表设计

**选择：** Ant Design Table 组件，列：手机号、昵称、角色、状态、注册时间、操作（查看详情、禁用/启用）。支持按状态筛选、按手机号搜索、分页。

**理由：** Ant Design Table 已内置筛选、排序、分页，与现有 admin-web 技术栈一致。

### D7: Admin-web 不实现用户编辑

**选择：** 管理端只查看用户信息和修改状态（禁用/启用），不编辑昵称/头像等个人资料。

**理由：** 个人资料修改由用户在 App 端自行完成，管理端不应越权修改用户个人信息。

## Risks / Trade-offs

- **[App 首次启动体验]** 新增登录流程后，新用户首次使用需先注册。→ 注册流程简化，仅需手机号+密码，3 步完成
- **[Token 安全]** SecureStore 虽安全，但越狱/Root 设备仍可被提取。→ 接受风险，后续可加固（设备指纹绑定）
- **[Admin API 无审计日志]** 管理员禁用用户无操作记录。→ 后续迭代增加 admin_audit_logs 表
- **[并发禁用竞争]** 管理员禁用用户的同时用户正在请求。→ JWT 无状态，已签发的 token 在过期前仍然有效，接受短时窗口
