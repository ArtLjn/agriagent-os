## ADDED Requirements

### Requirement: API 鉴权分类
系统 SHALL 将每个 HTTP API 路由归入且仅归入一个主要鉴权分类：公开接口、登录用户接口、农场资源接口或管理员接口。未归类接口 SHALL 被视为不合规。

#### Scenario: 新增路由必须归类
- **WHEN** 开发者新增 HTTP API 路由
- **THEN** 路由必须出现在公开白名单中，或通过 `get_current_user`、`get_current_farm`、`require_admin` 中的至少一种依赖进行保护

#### Scenario: 未归类路由被审计发现
- **WHEN** 自动化测试扫描应用中的全部 HTTP API 路由
- **THEN** 测试 SHALL 报告未归类或未受保护的路由路径和方法

### Requirement: 公开接口白名单
系统 SHALL 只允许明确白名单中的接口匿名访问。公开接口 SHALL 不返回用户私有数据、农场私有数据、运维数据、Prompt 内容、Trace 内容或可改变系统状态的管理操作。

#### Scenario: 白名单公开接口匿名访问
- **WHEN** 匿名请求访问 `/health`、`/auth/register`、`/auth/login`、`/api/app/version`、`/weather/forecast` 或 `/planting/operation-types`
- **THEN** 系统 MAY 在参数合法时返回 2xx 响应，且不得要求 Bearer token

#### Scenario: 非白名单接口匿名访问
- **WHEN** 匿名请求访问任何未列入公开白名单的业务或管理接口
- **THEN** 系统 SHALL 返回 401，并包含结构化认证错误码

### Requirement: 管理接口管理员鉴权
系统 SHALL 要求所有 `/admin/*` 管理接口携带有效 Bearer token，且 token 对应用户必须具备管理员角色。

#### Scenario: 匿名访问管理接口
- **WHEN** 匿名请求访问 `/admin/skills`、`/admin/prompts`、`/admin/config`、`/admin/cache/clear`、`/admin/prompts/reload`、`/admin/traces`、`/admin/traces/{request_id}/timeline`、`/admin/traces/{request_id}/nodes/{node_id}`、`/admin/guardrails-logs` 或 `/admin/users`
- **THEN** 系统 SHALL 返回 401，并包含结构化认证错误码

#### Scenario: 普通用户访问管理接口
- **WHEN** 普通登录用户请求访问任意 `/admin/*` 管理接口
- **THEN** 系统 SHALL 返回 403，并包含 `AUTH_ADMIN_REQUIRED` 错误码

#### Scenario: 管理员访问管理接口
- **WHEN** 管理员携带有效 Bearer token 请求访问 `/admin/*` 管理接口
- **THEN** 系统 SHALL 按接口业务逻辑处理请求

### Requirement: 农场资源对象级授权
系统 SHALL 对农场资源接口执行对象级授权，用户只能访问、修改或删除自己关联农场下的资源。

#### Scenario: 当前用户访问自己农场资源
- **WHEN** 登录用户请求访问自己农场下的成本、作物、周期、日志、债务、种植单元、工人、工资、作业单、会话、报告或仿真记录
- **THEN** 系统 SHALL 按接口业务逻辑处理请求

#### Scenario: 当前用户访问其他农场资源
- **WHEN** 登录用户请求访问、修改或删除其他农场下的资源 ID
- **THEN** 系统 SHALL 返回 403 或 404，且不得返回该资源的私有内容

### Requirement: Bearer Token 传递方式
系统 SHALL 使用 `Authorization: Bearer <token>` 作为受保护接口的访问令牌传递方式。

#### Scenario: 携带有效 Bearer token
- **WHEN** 客户端请求受保护接口并携带有效 `Authorization: Bearer <token>` 请求头
- **THEN** 系统 SHALL 从该 token 解析当前用户并继续执行对应权限校验

#### Scenario: 缺少 Bearer 前缀
- **WHEN** 客户端请求受保护接口但未携带 `Authorization` 头或未使用 `Bearer ` 前缀
- **THEN** 系统 SHALL 返回 401，并包含 `AUTH_MISSING_TOKEN` 错误码
