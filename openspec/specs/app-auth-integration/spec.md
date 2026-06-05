## Purpose

定义 App 端认证接入能力的行为要求。

## Requirements

### Requirement: 登录接入
FarmManagerMobile SHALL 提供手机号和密码登录流程，并在登录成功后保存后端返回的访问令牌。

#### Scenario: 登录成功
- **WHEN** 用户输入合法手机号和密码并调用 `POST /auth/login` 成功
- **THEN** App SHALL 保存 `access_token`，获取当前用户信息，并进入主界面

#### Scenario: 登录失败
- **WHEN** `POST /auth/login` 返回认证失败
- **THEN** App SHALL 展示错误提示，并保持用户在登录页面

### Requirement: 注册接入
FarmManagerMobile SHALL 提供手机号、密码、确认密码和可选昵称的注册流程。

#### Scenario: 注册成功
- **WHEN** 用户填写合法注册信息并调用 `POST /auth/register` 成功
- **THEN** App SHALL 保存 `access_token` 并进入主界面

#### Scenario: 注册输入无效
- **WHEN** 手机号格式不合法、密码不足 8 位或两次密码不一致
- **THEN** App SHALL 阻止提交并展示对应错误提示

### Requirement: 个人中心
FarmManagerMobile SHALL 提供个人中心页面展示当前用户信息，并支持更新昵称和退出登录。

#### Scenario: 查看个人信息
- **WHEN** 用户已登录并进入个人中心
- **THEN** App SHALL 展示昵称、手机号、角色和头像占位或头像地址

#### Scenario: 更新昵称
- **WHEN** 用户修改昵称并调用 `PUT /auth/me` 成功
- **THEN** App SHALL 更新本地用户状态并展示最新昵称

#### Scenario: 退出登录
- **WHEN** 用户确认退出登录
- **THEN** App SHALL 清除本地 token 和用户信息，并返回登录流程

### Requirement: Token 存储和注入
FarmManagerMobile SHALL 安全保存 JWT access token，并在请求受保护 API 时注入 `Authorization: Bearer <token>` 请求头。

#### Scenario: 请求受保护接口
- **WHEN** App 已保存有效 token 并请求受保护 API
- **THEN** API client SHALL 添加 `Authorization: Bearer <token>` 请求头

#### Scenario: 请求公开接口
- **WHEN** App 请求注册、登录、健康检查、版本检查、天气预报或通用作业类型接口
- **THEN** API client MAY 不携带 `Authorization` 请求头

### Requirement: Token 过期处理
FarmManagerMobile SHALL 在 token 缺失、无效或过期时引导用户重新登录。

#### Scenario: 受保护 API 返回 401
- **WHEN** 受保护 API 返回 401
- **THEN** App SHALL 清除本地 token 和用户信息，并跳转到登录页面

#### Scenario: App 启动校验 token
- **WHEN** App 启动且本地存在 token
- **THEN** App SHALL 调用 `GET /auth/me` 校验 token 有效性，并根据结果进入主界面或登录流程
