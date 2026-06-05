## Context

后端当前使用 FastAPI 依赖注入完成鉴权：`get_current_user` 校验 Bearer JWT，`get_current_farm` 在用户鉴权后绑定当前用户农场，`require_admin` 校验管理员角色。业务接口大多已经使用 `get_current_farm`，但部分 `/admin/*` 接口仅依赖 `get_db` 或完全无依赖，导致匿名用户可访问运维数据和执行运维操作。

成熟 API 鉴权设计通常包含四条基线：默认拒绝、逐请求鉴权、功能级权限校验、对象级权限校验。本项目不需要引入复杂 RBAC 权限矩阵，当前角色只有普通用户和管理员，因此可以用“路由分类 + 依赖约束 + 审计测试”解决主要风险。

## Goals / Non-Goals

**Goals:**
- 建立全量 API 鉴权分类：公开、登录用户、农场资源、管理员。
- 将管理接口默认改为管理员鉴权，修复当前匿名访问的 admin config、admin trace 和 guardrails log。
- 用自动化测试保证新增路由必须明确落入某个鉴权分类。
- 保持现有 JWT、农场隔离和 admin-web token 注入方式不变。

**Non-Goals:**
- 不引入新的身份提供商、OAuth 授权服务器或 refresh token 体系。
- 不实现细粒度 RBAC/ABAC 权限模型。
- 不改变用户表角色模型。
- 不把所有公开接口强制改为登录接口，除非该接口泄露用户或运维数据。

## Decisions

### 1. 使用显式路由分类，不做全局登录中间件

**选择**: 保持 FastAPI 依赖注入模式，为每个路由或 router 标注合适依赖；新增测试从 app routes 中提取实际路由并校验分类。

**理由**: 当前项目已有 `get_current_user`、`get_current_farm`、`require_admin`，继续使用本地模式改动最小。全局中间件会让注册、登录、健康检查、版本检查等公开接口需要额外绕过，容易形成隐藏例外。

**替代方案**: 添加全局认证中间件，再维护公开白名单。该方案集中但迁移风险更高，且 FastAPI dependency override 测试会更难维护。

### 2. `/admin/*` 默认管理员鉴权，公开例外必须显式论证

**选择**: `admin_config.py`、`admin_trace.py`、`admin.py` 的 router 使用 `dependencies=[Depends(require_admin)]`，已有 `admin_stats.py` 和 `admin_users.py` 保持现状。

**理由**: 管理路由包含 Prompt 内容、Trace 输入输出、Token 用量、用户管理、缓存清理等敏感操作，符合函数级授权保护范围。router 级依赖可减少单接口漏标。

**替代方案**: 在每个 endpoint 参数中添加 `_admin: User = Depends(require_admin)`。这种方式更显式，但重复多，后续新增接口更容易漏掉。

### 3. 公开接口采用固定白名单

**选择**: 公开接口白名单暂定为 `/health`、`/auth/register`、`/auth/login`、`/api/app/version`、`/weather/forecast`、`/planting/operation-types`。

**理由**: 这些接口不依赖当前用户资源，且 App 启动、登录前天气展示或内置作业类型选择可能需要匿名访问。公开接口必须在测试白名单中列出，新增公开接口需要更新测试和说明。

**替代方案**: 要求天气和作业类型也登录访问。更严格，但会改变移动端登录前体验；本提案先不扩大行为变更。

### 4. 对象级授权继续以 farm_id 隔离为主

**选择**: 业务资源接口继续使用 `get_current_farm`，服务层查询必须带 `farm.id` 或通过当前用户上下文限定资源。含路径 ID 的接口应有测试覆盖“跨农场资源不可访问”。

**理由**: OWASP API 安全风险中对象级授权是高频问题。当前项目的农场资源天然以 `farm_id` 归属，沿用该边界最符合现有模型。

**替代方案**: 在所有资源表添加 owner_user_id 并改为用户级隔离。当前数据模型已存在 farm 层，不需要重复所有权字段。

### 5. 审计测试作为安全传感器

**选择**: 新增一组路由鉴权分类测试，扫描 `app.routes`，排除文档/OpenAPI 内置路由后，断言每个 API 路由至少满足以下之一：公开白名单、含 `get_current_user`、含 `get_current_farm`、含 `require_admin`。同时为 admin 未授权路径增加 401/403/200 行为测试。

**理由**: 这类问题最容易在新增接口时回归。比单靠人工 review 更稳定，也符合项目 Guide+Sensor 的约束风格。

**替代方案**: 手写 Markdown 接口清单人工维护。可读性高但容易过期，建议作为辅助文档而不是唯一保障。

## Risks / Trade-offs

- [Risk] admin-web 某些页面未登录时从 200 变为 401，可能暴露前端错误态不足。→ Mitigation: 确认 `api/client.ts` 已统一注入 Bearer token，并补充未登录跳转/错误处理检查。
- [Risk] 测试 fixture 当前全局 override `get_current_user`，可能掩盖真实 401。→ Mitigation: 鉴权行为测试应清理 dependency overrides 或使用独立 app/client。
- [Risk] router 级依赖在静态扫描中不如函数参数直观。→ Mitigation: 审计测试读取 FastAPI route dependency graph，而不是只做源码字符串匹配。
- [Risk] 公开白名单可能过宽。→ Mitigation: 每个公开接口在 spec 中列出原因；新增公开接口必须更新白名单测试。

## Migration Plan

1. 给缺失保护的 admin routers 添加 `require_admin` router 级依赖。
2. 调整 admin config、admin trace、guardrails log 测试，覆盖匿名、普通用户、管理员三类访问。
3. 新增全量路由鉴权分类审计测试。
4. 运行后端 API 测试和 lint。
5. 如 admin-web 出现未登录调用 401，确认 AuthGuard 和 axios interceptor 行为；无需后端回滚。

Rollback 策略：如上线后发现管理员页面无法访问，优先检查 token 注入和管理员角色；必要时可临时仅回滚对应 router 级依赖，但不得长期保持匿名 admin 接口。
