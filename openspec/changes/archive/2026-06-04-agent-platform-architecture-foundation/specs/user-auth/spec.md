## ADDED Requirements

### Requirement: Token payload 标准化
系统 SHALL 签发包含 `sub`、`type`、`iat`、`exp`、`jti` 的 access token。`sub` 表示用户 ID，`type` SHALL 为 `access`。

#### Scenario: 签发 access token
- **WHEN** 用户登录成功
- **THEN** 返回的 JWT payload 包含 `sub`、`type=access`、`iat`、`exp`、`jti`

### Requirement: 统一 Auth 错误响应
认证相关接口和依赖 SHALL 返回包含 `code` 和 `detail` 的结构化错误响应。

#### Scenario: 无 token
- **WHEN** 受保护接口未携带 Authorization 头
- **THEN** 返回 401，响应包含 `code=AUTH_MISSING_TOKEN`

#### Scenario: 权限不足
- **WHEN** 普通用户访问管理员接口
- **THEN** 返回 403，响应包含 `code=AUTH_ADMIN_REQUIRED`

### Requirement: Auth 依赖模块化
系统 SHALL 从 Auth 模块提供 `get_current_user` 和 `require_admin` 依赖。旧依赖入口如继续存在，SHALL 只作为兼容 re-export。

#### Scenario: 新接口使用 Auth 依赖
- **WHEN** 开发者新增需要认证的接口
- **THEN** 接口从 Auth 模块导入当前用户或管理员依赖
