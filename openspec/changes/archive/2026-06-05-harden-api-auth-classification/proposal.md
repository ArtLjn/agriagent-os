## Why

当前后端多数业务接口已经通过 JWT 用户鉴权或农场级隔离保护，但部分 `/admin/*` 运维接口仍可匿名访问，导致管理功能、Prompt 内容、Trace 输入输出、运行时配置和缓存操作暴露在未授权访问面上。成熟 API 安全基线也把函数级鉴权和对象级鉴权列为核心风险，需要用统一分类和自动化检查补齐。

## What Changes

- 为所有 HTTP API 建立显式鉴权分类：公开、登录用户、农场资源、管理员。
- 将管理后台和运维接口默认收敛到管理员鉴权，特别是 `/admin/skills`、`/admin/prompts`、`/admin/config`、`/admin/cache/clear`、`/admin/prompts/reload`、`/admin/traces*`、`/admin/guardrails-logs`。
- 保留必要公开接口，但必须显式列入公开白名单，例如健康检查、注册登录、App 版本检查、天气查询和通用作业类型。
- 为包含对象 ID 的业务接口确认对象级授权：用户只能访问自己农场下的数据，管理员接口只能由管理员访问。
- 增加鉴权分类审计测试，防止新增路由默认为匿名可访问。
- 更新相关 API 测试，从“匿名访问 200”改为“匿名 401、普通用户 403、管理员 200”。

## Capabilities

### New Capabilities
- `api-auth-classification`: 定义 API 鉴权分类、默认拒绝策略、管理员接口保护和对象级授权审计要求。

### Modified Capabilities
- `app-auth-integration`: App 端请求继续使用 Bearer token，并明确公开接口与受保护接口的行为差异。
- `admin-user-api`: 管理 API 统一要求管理员鉴权，补齐此前仅部分 admin 接口受保护的不一致。
- `trace-monitor-ui`: Trace 查询和清理接口必须通过管理员鉴权后访问。

## Impact

- 后端 API：`backend/app/api/admin_config.py`、`backend/app/api/admin_trace.py`、`backend/app/api/admin.py`、路由审计测试。
- 后端鉴权依赖：继续复用 `get_current_user`、`get_current_farm`、`require_admin`。
- 测试：调整 admin config、admin trace、guardrails log、全量路由鉴权分类测试。
- 前端：admin-web 已通过统一 API client 注入 `Authorization: Bearer <token>`，正常登录态应不受影响；未登录访问 admin 页面对应接口会返回 401。
- 安全基线参考：OWASP API Security Top 10 2023 的 BOLA/BFLA、OWASP Authorization Cheat Sheet 的默认拒绝和逐请求鉴权、RFC 6750 的 Bearer token header 用法、NIST SP 800-63B 的 bearer session secret 保护原则。
