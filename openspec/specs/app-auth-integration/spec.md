# App 端认证接入

## 概述
FarmManagerMobile 接入后端多用户认证系统，实现注册/登录/个人中心功能。

## 功能模块

### 登录页面 (LoginScreen)

**UI 元素：**
- App Logo/标题
- 手机号输入框（numeric keyboard，maxLength=11）
- 密码输入框（secureTextEntry）
- 登录按钮（禁用条件：手机号不满11位或密码空）
- "还没有账号？去注册" 文本链接
- 错误提示区域（API 错误消息）

**流程：**
1. 用户输入手机号 + 密码
2. 前端校验：手机号正则 `^1[3-9]\d{9}$`，密码非空
3. 调用 `POST /auth/login`
4. 成功：存储 token → 调用 `GET /auth/me` 获取用户信息 → 跳转主界面
5. 失败：展示错误消息（手机号或密码错误）

### 注册页面 (RegisterScreen)

**UI 元素：**
- 手机号输入框
- 密码输入框（提示：至少8位）
- 确认密码输入框
- 昵称输入框（可选，placeholder="农友"）
- 注册按钮
- "已有账号？去登录" 文本链接

**流程：**
1. 用户填写信息
2. 前端校验：手机号格式、密码≥8位、两次密码一致
3. 调用 `POST /auth/register`
4. 成功：存储 token → 跳转主界面
5. 失败：展示错误消息（手机号已注册等）

### 个人中心页面 (ProfileScreen)

**UI 元素：**
- 头像区域（默认占位图）
- 昵称（可点击编辑）
- 手机号（只读）
- 角色（只读）
- 退出登录按钮

**交互：**
- 点击昵称 → 弹出编辑框 → 调用 `PUT /auth/me` → 更新本地状态
- 点击退出登录 → Alert 二次确认 → 清除 token → 跳转登录页

### Token 管理

**存储：**
- 使用 `expo-secure-store` 存储 JWT token
- Key: `farm_manager_auth_token`

**注入：**
- 修改 `api/client.ts`，每次请求前从 SecureStore 读取 token
- 添加 `Authorization: Bearer <token>` header

**过期处理：**
- API 收到 401 响应 → 清除 token → 跳转登录页
- App 启动时调用 `GET /auth/me` 验证 token 有效性

## 导航调整

**AppNavigator.tsx：**
```
启动 → loadToken()
  ├─ token 有效 → MainTabNavigator
  └─ token 无效/无 token → AuthStack (Login/Register)
```

**AuthStack：**
- LoginScreen（默认）
- RegisterScreen

## 技术约束
- 使用现有 API client 封装
- 使用 Zustand 管理认证状态（与现有 stores/* 一致）
- React Navigation 处理页面跳转
- 登录后清除 AuthStack，防止返回键回到登录页
