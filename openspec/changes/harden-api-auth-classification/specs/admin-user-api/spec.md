## ADDED Requirements

### Requirement: 管理 API 统一管理员鉴权
所有 `/admin/*` API SHALL 要求有效管理员 Bearer token，包括用户管理、Token 统计、配置查看、Skill/Prompt 查看、缓存清理、Prompt 热加载、Trace 查询、Trace 清理和 Guardrails 日志查询。

#### Scenario: 匿名访问任意管理 API
- **WHEN** 请求未携带有效 Bearer token 访问任意 `/admin/*` API
- **THEN** 系统 SHALL 返回 401，并不得返回管理数据或执行管理操作

#### Scenario: 普通用户访问任意管理 API
- **WHEN** 普通用户携带有效 Bearer token 访问任意 `/admin/*` API
- **THEN** 系统 SHALL 返回 403，并不得返回管理数据或执行管理操作

#### Scenario: 管理员访问任意管理 API
- **WHEN** 管理员携带有效 Bearer token 访问任意 `/admin/*` API
- **THEN** 系统 SHALL 按接口业务逻辑返回结果或执行操作

### Requirement: 管理接口敏感响应保护
管理接口 SHALL 只在管理员鉴权通过后返回运行时配置、Prompt 内容、Skill 参数、Trace 输入输出、Guardrails 日志、用户列表或 Token 用量数据。

#### Scenario: 未授权读取敏感管理数据
- **WHEN** 匿名用户或普通用户请求包含敏感管理数据的接口
- **THEN** 系统 SHALL 在查询数据源前拒绝请求
