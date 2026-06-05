## ADDED Requirements

### Requirement: 受保护 API 携带 Bearer token
App 和管理端客户端 SHALL 在请求受保护 API 时携带 `Authorization: Bearer <token>` 请求头。公开白名单接口 MAY 不携带 token。

#### Scenario: 登录后请求业务接口
- **WHEN** 用户登录成功并请求成本、作物、周期、日志、债务、种植、Agent、设置或仿真接口
- **THEN** 客户端 SHALL 在请求头中携带 `Authorization: Bearer <token>`

#### Scenario: 登录前请求公开接口
- **WHEN** 客户端在未登录状态请求注册、登录、健康检查、App 版本、天气预报或通用作业类型接口
- **THEN** 客户端 MAY 不携带 `Authorization` 请求头

### Requirement: 认证失败处理
客户端 SHALL 对受保护 API 返回的 401 认证失败响应执行退出登录或重新登录流程。

#### Scenario: Token 缺失或过期
- **WHEN** 受保护 API 返回 401
- **THEN** 客户端 SHALL 清除本地 token 并引导用户重新登录
