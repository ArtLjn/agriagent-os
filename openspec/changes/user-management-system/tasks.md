## 1. 后端 — Admin 用户管理 API

- [ ] 1.1 创建 `app/schemas/admin_user.py`：
  - `AdminUserListItem`：id, phone, nickname, avatar_url, role, status, created_at, farm_name
  - `AdminUserListResponse`：items, total
  - `AdminUserDetailResponse`：同上 + farm_id, farm_location
  - `UpdateUserStatusRequest`：status (active/disabled)
- [ ] 1.2 创建 `app/api/admin_users.py`：
  - `GET /admin/users` — 用户列表，支持 query: page, size, status, phone_keyword
  - `GET /admin/users/{user_id}` — 用户详情
  - `PUT /admin/users/{user_id}/status` — 修改用户状态（禁用/启用）
  - 所有接口使用 `require_admin` 依赖
- [ ] 1.3 在 `app/main.py` 注册 `admin_users` 路由
- [ ] 1.4 测试：列表分页、按状态筛选、按手机号搜索、详情返回、状态修改、非管理员 403

## 2. 后端 — Admin 角色校验依赖

- [ ] 2.1 确认 `app/api/deps.py` 中 `require_admin` 已实现（从 storage-redesign-multi-user 继承）
- [ ] 2.2 若未实现，补充 `require_admin` 依赖：校验 `get_current_user` 返回的 user.role == "admin"
- [ ] 2.3 测试：普通用户访问 admin 接口返回 403

## 3. admin-web — 用户管理 API 层

- [ ] 3.1 创建 `admin-web/src/api/users.ts`：
  - `listUsers(params)` → `GET /admin/users`
  - `getUserDetail(userId)` → `GET /admin/users/{user_id}`
  - `updateUserStatus(userId, status)` → `PUT /admin/users/{user_id}/status`
  - 定义 TypeScript 接口（与后端 schema 对应）
- [ ] 3.2 测试：API 函数类型正确

## 4. admin-web — 用户列表页面

- [ ] 4.1 创建 `admin-web/src/pages/Users/index.tsx`：
  - Ant Design Table 展示用户列表
  - 列：手机号、昵称、角色、状态（带颜色标签）、注册时间、操作
  - 状态筛选器（全部/正常/已禁用）
  - 手机号搜索框
  - 分页器
  - 操作列：查看详情按钮、禁用/启用按钮
- [ ] 4.2 状态标签颜色：active → 绿色，disabled → 红色
- [ ] 4.3 禁用/启用操作需二次确认（Modal.confirm）
- [ ] 4.4 更新 `admin-web/src/App.tsx` 添加 `/users` 路由
- [ ] 4.5 更新 `admin-web/src/layouts/AdminLayout.tsx` 添加"用户管理"导航项

## 5. admin-web — 用户详情弹窗

- [ ] 5.1 创建用户详情 Modal 组件（内嵌在 Users 页面或独立组件）
  - 展示：ID、手机号、昵称、头像、角色、状态、注册时间
  - 展示关联农场信息：农场名、位置
  - 底部操作：禁用/启用按钮
- [ ] 5.2 点击列表"查看详情"打开 Modal

## 6. FarmManagerMobile — 认证存储层

- [ ] 6.1 安装 `expo-secure-store` 依赖
- [ ] 6.2 创建 `FarmManagerMobile/src/stores/authStore.ts`：
  - `token: string | null` — 当前 JWT
  - `user: UserProfile | null` — 当前用户信息
  - `isLoggedIn: boolean`
  - `login(token, user)` — 存储 token 到 SecureStore，设置用户信息
  - `logout()` — 清除 SecureStore，清空状态
  - `loadToken()` — 从 SecureStore 读取 token，调用 `/auth/me` 验证
- [ ] 6.3 创建 `FarmManagerMobile/src/types/auth.ts`：UserProfile 类型定义

## 7. FarmManagerMobile — API 客户端注入 Token

- [ ] 7.1 修改 `FarmManagerMobile/src/api/client.ts`：
  - 每次请求从 authStore 读取 token
  - 有 token 时添加 `Authorization: Bearer <token>` header
  - 收到 401 响应时，调用 authStore.logout() 并跳转登录页
- [ ] 7.2 测试：token 正确注入，401 正确处理

## 8. FarmManagerMobile — 登录页面

- [ ] 8.1 创建 `FarmManagerMobile/src/screens/auth/LoginScreen.tsx`：
  - 手机号输入框（数字键盘，11 位限制）
  - 密码输入框（安全文本）
  - 登录按钮
  - "还没有账号？去注册"链接
  - 错误提示（手机号格式错误、密码错误等）
- [ ] 8.2 登录流程：调用 `POST /auth/login` → 存储 token → 调用 `GET /auth/me` → 跳转主界面
- [ ] 8.3 更新导航：App 启动时检查登录态，未登录显示登录页

## 9. FarmManagerMobile — 注册页面

- [ ] 9.1 创建 `FarmManagerMobile/src/screens/auth/RegisterScreen.tsx`：
  - 手机号输入框
  - 密码输入框（≥8 位提示）
  - 确认密码输入框
  - 昵称输入框（可选，默认"农友"）
  - 注册按钮
  - "已有账号？去登录"链接
  - 错误提示（手机号已注册、密码不一致等）
- [ ] 9.2 注册流程：调用 `POST /auth/register` → 存储 token → 跳转主界面

## 10. FarmManagerMobile — 个人中心页面

- [ ] 10.1 创建 `FarmManagerMobile/src/screens/auth/ProfileScreen.tsx`（或修改现有 SettingsScreen）：
  - 展示：头像、昵称、手机号
  - 编辑昵称功能
  - 退出登录按钮（二次确认）
  - 点击昵称可修改（调用 `PUT /auth/me`）
- [ ] 10.2 退出登录：清除 token → 跳转登录页
- [ ] 10.3 在 MainTabNavigator 的 Settings tab 中新增"个人中心"入口

## 11. FarmManagerMobile — 启动流程与导航调整

- [ ] 11.1 修改 `AppNavigator.tsx`：
  - 新增 AuthStack（LoginScreen、RegisterScreen）
  - 启动时调用 authStore.loadToken() 判断登录态
  - 已登录 → MainTabNavigator
  - 未登录 → AuthStack
- [ ] 11.2 确保登录后按返回键不回到登录页

## 12. 端到端验证

- [ ] 12.1 后端测试：全量 pytest 通过
- [ ] 12.2 admin-web 测试：用户列表加载、筛选、分页、禁用/启用流程正常
- [ ] 12.3 App 测试：注册 → 登录 → 查看个人中心 → 修改昵称 → 退出登录 → 重新登录
- [ ] 12.4 App 测试：Token 过期后自动跳转登录页
- [ ] 12.5 App 测试：禁用用户后 token 失效，下次请求返回 401
- [ ] 12.6 跨端验证：App 注册的用户在 admin-web 用户列表中可见
