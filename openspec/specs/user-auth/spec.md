## ADDED Requirements

### Requirement: 用户注册
系统 SHALL 提供手机号 + 密码注册接口。密码 MUST 使用 bcrypt 哈希存储（盐轮次 ≥ 12）。注册成功后自动创建默认农场（name="我的农场"）并签发 JWT token。

#### Scenario: 正常注册
- **WHEN** 用户提交 `POST /auth/register`，body 为 `{"phone": "13800138001", "password": "mypassword123", "nickname": "老李"}`
- **THEN** 系统创建 User 记录（phone 唯一），创建 Farm 记录（user_id 关联），返回 `{"token": "<jwt>", "user": {...}}`

#### Scenario: 手机号已注册
- **WHEN** 用户提交注册，phone 已存在
- **THEN** 返回 409，message 为"手机号已注册"

#### Scenario: 手机号格式错误
- **WHEN** 用户提交 phone 不匹配 `^1[3-9]\d{9}$`
- **THEN** 返回 422 校验错误

#### Scenario: 密码过短
- **WHEN** 用户提交密码长度 < 8
- **THEN** 返回 422 校验错误

### Requirement: 用户登录
系统 SHALL 提供手机号 + 密码登录接口，验证通过后签发 JWT token（有效期 7 天，payload 含 user_id）。

#### Scenario: 正常登录
- **WHEN** 用户提交 `POST /auth/login`，body 为 `{"phone": "13800138001", "password": "mypassword123"}`
- **THEN** 验证密码正确，返回 `{"token": "<jwt>", "user": {...}}`

#### Scenario: 密码错误
- **WHEN** 用户提交正确手机号但密码不匹配
- **THEN** 返回 401，message 为"手机号或密码错误"

#### Scenario: 用户不存在
- **WHEN** 用户提交未注册的手机号
- **THEN** 返回 401，message 为"手机号或密码错误"（不透露用户是否存在）

### Requirement: JWT 认证中间件
所有需要认证的 API 端点 SHALL 从 `Authorization: Bearer <token>` 头读取 JWT，解析 user_id。token 无效或过期时返回 401。

#### Scenario: 有效 token
- **WHEN** 请求携带有效 JWT，payload 含 user_id
- **THEN** 中间件将 user_id 注入请求上下文，请求继续处理

#### Scenario: token 过期
- **WHEN** 请求携带的 JWT 已超过 7 天
- **THEN** 返回 401，message 为"登录已过期，请重新登录"

#### Scenario: 无 token
- **WHEN** 请求未携带 Authorization 头
- **THEN** 返回 401，message 为"未提供认证信息"

#### Scenario: 用户已禁用
- **WHEN** 请求携带有效 JWT，但对应用户 status != "active"
- **THEN** 返回 401，message 为"用户不存在或已禁用"

### Requirement: 统一权限过滤器
系统 SHALL 通过 FastAPI 依赖链实现三层权限过滤：Layer 1 认证（get_current_user）→ Layer 2 租户隔离（get_current_farm）→ Layer 3 资源归属/角色校验。

#### Scenario: 普通业务接口自动注入
- **WHEN** 接口声明 `farm: Farm = Depends(get_current_farm)`
- **THEN** 系统自动完成 JWT 解析 → User 查询 → Farm 查询，接口直接获得已验证的 farm 对象

#### Scenario: 资源型接口归属校验
- **WHEN** 用户访问 `GET /conversations/{session_id}/messages`，该会话属于另一个 farm
- **THEN** 返回 403，message 为"无权访问此资源"

#### Scenario: 管理接口角色校验
- **WHEN** 普通用户（role="user"）访问管理接口（如 /admin/training-data）
- **THEN** 返回 403，message 为"需要管理员权限"

#### Scenario: 公开接口无需认证
- **WHEN** 请求访问 /auth/register、/auth/login、/health
- **THEN** 不经过任何过滤器，直接处理

### Requirement: get_current_farm 验证归属
`get_current_farm` 依赖 SHALL 通过 `Farm.user_id == current_user.id` 查询农场，确保农场属于当前用户。查询不到时返回 404。

#### Scenario: 正常获取农场
- **WHEN** 用户已认证，且有关联农场
- **THEN** 返回 Farm 对象

#### Scenario: 用户无农场
- **WHEN** 用户已认证，但 farms 表中无 user_id 匹配的记录
- **THEN** 返回 404，message 为"未找到关联农场"

### Requirement: OAuth 绑定预留
系统 SHALL 创建 `user_oauth` 表（user_id, provider, provider_uid, provider_data），当前不实现绑定逻辑。表结构为未来接入微信/支付宝 OAuth 预留。

#### Scenario: OAuth 表存在但不可用
- **WHEN** 用户尝试通过 OAuth 登录
- **THEN** 返回 501，message 为"OAuth 登录暂未开放"
