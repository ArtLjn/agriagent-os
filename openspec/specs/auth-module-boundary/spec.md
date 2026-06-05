## Purpose

定义 auth-module-boundary 能力的行为要求。

## Requirements

### Requirement: Auth 独立安全边界
系统 SHALL 将认证鉴权能力集中在 Auth 模块中。Auth 模块 SHALL 管理登录、注册、密码哈希、token 签发与验证、当前用户依赖、管理员权限和认证错误码。

#### Scenario: 查找认证逻辑
- **WHEN** 开发者需要修改 JWT 验证逻辑
- **THEN** 修改发生在 Auth 模块，而不是 API 路由或通用依赖文件中

### Requirement: Farm 上下文与 Auth 分离
当前农场依赖 SHALL 属于 Farm 模块，并通过 Auth 模块提供的当前用户依赖组合得到。Auth 模块 SHALL NOT 直接承担当前农场解析职责。

#### Scenario: 业务接口注入当前农场
- **WHEN** 业务接口声明当前农场依赖
- **THEN** 系统先通过 Auth 解析当前用户，再由 Farm 模块解析该用户关联的农场

### Requirement: Auth 与业务创建解耦
注册成功后创建默认农场 SHALL 通过 Farm 模块接口完成。Auth 模块 SHALL NOT 直接绕过 Farm 模块操作 Farm 业务规则。

#### Scenario: 注册创建默认农场
- **WHEN** 新用户注册成功
- **THEN** Auth 调用 Farm 模块创建默认农场，并返回 token 与用户信息

### Requirement: 认证错误码
Auth 模块 SHALL 为认证失败、token 过期、token 无效、用户禁用、权限不足和管理员权限不足提供稳定错误码。

#### Scenario: token 过期
- **WHEN** 请求携带过期 token
- **THEN** 响应包含认证错误码和用户可理解的错误信息
