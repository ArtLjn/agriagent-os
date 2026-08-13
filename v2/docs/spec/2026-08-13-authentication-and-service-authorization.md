---
last_updated: 2026-08-13
status: proposed
---

# v2 用户鉴权与服务间鉴权设计

> Spec ID: 2026-08-13-authentication-and-service-authorization  
> 适用范围：`agent`、`business REST`、`business MCP`、Web/Mobile 客户端  
> 目标：建立“用户身份”和“服务身份”分离、可验证、可审计、不可静默降级的鉴权体系。

## 1. 背景与问题

当前 v2 存在两类调用链：

```text
Web/Mobile ── User JWT ──> Agent /chat ── MCP ──> Business
Web/Mobile ── User JWT ─────────────────────────> Business REST
```

现有设计把 Agent 调 Business 的服务令牌和用户上下文拆成：

```text
X-Agent-Token + X-User-Id + X-Farm-Id
```

该方案有以下缺陷：

1. `X-User-Id`、`X-Farm-Id` 是普通 Header，Business 无法确认它们是否由可信服务产生。
2. Agent JWT 解析失败时不能回退到默认用户或默认农场，否则会造成越权和数据串租户。
3. 用户 JWT 密钥、Agent 服务密钥和 Business MCP 信任边界没有明确分离。
4. 当前 `agent_token` 为空时，调用链仍可能继续执行，错误会在业务工具层才暴露。
5. 服务间调用缺少 audience、issuer、过期时间、请求链路和调用主体信息，审计无法可靠还原。

本规范采用双层模型：

- 用户请求使用 User Access Token 证明“谁在操作”。
- 服务间请求使用 Service Token 证明“哪个服务在调用”。
- Agent 代用户访问 Business 时，再携带短时效 Delegation Token 证明“服务代表哪个用户、哪个农场操作”。

## 2. 设计原则

### 2.0 先看结论：三个 Token 分工

本系统不是让前端同时携带三个 Token。浏览器只需要 User Access Token；另外两个 Token
由 Agent 在服务端内部处理，绝不能下发到浏览器：

| Token | 谁签发 | 谁持有 | 放在哪个请求 | 证明什么 | 前端是否需要知道 |
|---|---|---|---|---|---|
| User Access JWT | Business 登录接口 | 浏览器内存、Web/Mobile | 浏览器 → Agent/Business REST 的 `Authorization: Bearer` | “哪个用户正在操作哪个 `farm_uid`” | 需要 |
| Service Token | 运维配置/密钥系统 | Agent 服务 | Agent → Business MCP 的 `Authorization: Bearer` | “调用方是 Agent 服务” | 不需要 |
| Delegation JWT | Agent | Agent 服务、Business 入口短暂校验 | Agent → Business MCP 的 `X-Delegation-Token` | “Agent 代表哪个用户、农场和 turn” | 不需要 |

一次聊天请求的真实流转如下：

```text
浏览器选择开发用户
  └─ 获取 User Access JWT
       └─ POST /api/v2/chat
            Authorization: Bearer <User Access JWT>
                 ↓ Agent 校验用户 JWT
                 ├─ Authorization: Bearer <Service Token>
                 └─ X-Delegation-Token: <Delegation JWT>
                      ↓ Business MCP 校验服务身份、委托身份和数据库归属
                      └─ 使用内部 farm_id 执行业务 SQL
```

因此：

- 前端不应该自己生成 Service Token 或 Delegation Token；
- `farm_id` 不应该由前端提交来决定租户范围；
- 前端展示和接口返回优先使用 `farm_uid`；
- `/api/v2/dev-users` 仅是本地开发辅助入口，不是生产登录接口。

### 2.1 身份分离

用户身份、服务身份和委托身份必须使用不同的令牌和密钥：

| 身份 | 令牌 | 持有者 | 用途 |
|---|---|---|---|
| 用户身份 | User Access Token | Web/Mobile | 登录后访问 Agent、Business REST |
| 服务身份 | Service Token | Agent | Agent 访问 Business MCP |
| 用户委托 | Delegation Token | Agent 生成，Business 校验 | 证明 Agent 代表哪位用户/农场 |

Agent 不得持有用户 JWT 的签发私钥；Business 不得根据普通用户 Header 推断身份。

### 2.2 失败即拒绝

鉴权失败必须返回明确的 `401` 或 `403`，不得：

- 回退到 `default_farm_id`；
- 使用空字符串作为 `user_id` 继续执行；
- 将 Header 中的用户信息当作 JWT 校验失败后的补偿；
- 让未认证请求进入 LLM、MCP 或写操作流程。

### 2.3 身份先于业务

请求必须按以下顺序处理：

```text
提取凭证 → 校验签名/有效期/受众 → 校验用户状态和农场归属
→ 构造 Principal → 执行业务或 Agent 流程
```

业务 Service 只接受已验证的 `Principal` 或明确的 `farm_id`，不能重新解析 HTTP Header。

### 2.4 最小权限和短时效

- User Access Token 默认有效期 7 天；生产环境应支持刷新和主动吊销。
- Delegation Token 有效期不超过单个 turn 的预计最长执行时间，建议 5 分钟。
- Service Token 建议有效期 5～15 分钟；如暂时使用静态凭证，必须支持轮换和双密钥过渡。
- 令牌只声明必要 scope，不把密码、完整手机号、密钥等敏感信息写入 JWT。

## 3. 统一身份模型 Principal

### 3.1 外部 UID 与内部数据库 ID

当前 `v2/sql/farm_manager.sql` 的规范结构是：

| 实体 | 数据库字段 | 类型 | 定位 |
|---|---|---|---|
| 用户 | `users.id` | `varchar(36)` UUID | 用户主键，同时可作为稳定外部用户标识 |
| 农场 | `farms.id` | `int AUTO_INCREMENT` | 数据库内部主键，不作为 token 的对外标识 |
| 农场 | `farms.uid` | `varchar(36)` UUID | 稳定外部农场标识，作为 token 的 `farm_uid` |
| 关联 | `farms.user_id` | `varchar(36)` | 用户与默认农场的归属关系 |

因此不需要为了和农场字段对称而新增 `users.user_uid`，也不需要在 JWT 中额外增加 `user_uid` claim。`users.id` 已经满足 UUID 和稳定标识要求，JWT 使用标准 `sub` claim 承载它即可。

推荐的标识转换边界：

```text
JWT / Delegation Token：sub=user UUID，farm_uid=farm UUID
        ↓ Business 鉴权层
校验 users.id + farms.uid + farms.user_id
        ↓
内部 Principal：user_id=users.id，farm_uid=farms.uid，farm_id=farms.id
        ↓
业务 Service / SQL：只使用内部 farm_id 做外键查询
```

约束：

- User JWT 和 Delegation Token 不使用 `farm_id` 作为对外租户标识。
- `farm_id` 可以在内部 Principal、日志和 SQL 参数中存在，但不能由客户端或普通 Header 直接提供。
- 兼容迁移期间 Agent 当前仍会在 JWT 中保留 `farm_id`，仅用于 Redis/Mongo 旧状态的 scope 兼容；它不参与新的租户信任判断。待状态存储完全使用 `farm_uid` 后删除该 claim。
- 当前 DDL 的 `farms.user_id UNIQUE` 表示一个用户最多关联一个农场；如果未来一个用户可以拥有多个农场，必须通过用户-农场 membership 表选择当前 `farm_uid`，不能继续依赖这一对一结构。

所有入口在认证成功后构造统一的内部身份对象：

```python
Principal(
    subject_id="user-uuid",
    subject_type="user",
    farm_uid="farm-uuid",
    farm_id=1,
    role="user",
    scopes={"farm:read", "farm:write"},
    auth_method="user_jwt",
    issuer="farm-manager-auth",
    token_id="jwt-jti",
    actor_service=None,
)
```

Agent 委托 Business 时，Business 侧的 Principal 应包含：

```python
Principal(
    subject_id="user-uuid",
    subject_type="user",
    farm_uid="farm-uuid",
    farm_id=1,
    role="user",
    scopes={"farm:read"},
    auth_method="service_delegation",
    issuer="farm-manager-agent",
    token_id="delegation-jti",
    actor_service="agent",
)
```

`subject_id` 表示实际数据主体，`actor_service` 表示实际发起请求的服务。审计日志必须同时记录两者。

## 4. User Access Token 设计

### 4.1 使用边界

User Access Token 只允许出现在：

- Web/Mobile → Agent HTTP API；
- Web/Mobile → Business REST API；
- 需要用户身份的内部管理调用。

User Access Token 不应被 Agent 原样转发给 Business MCP。这样可以避免 Business 将 Agent 当作普通前端，也避免服务间共享用户令牌生命周期。

### 4.1.1 前端实际使用方式

前端只保存当前用户的 `access_token`，所有用户资源请求都统一发送：

```http
Authorization: Bearer <access_token>
```

需要携带 User Access Token 的 Agent 接口包括会话、聊天、审批、重置、turn 和 Trace：

```text
GET  /api/v2/conversations
GET  /api/v2/conversations/{conversation_id}
POST /api/v2/chat
POST /api/v2/approve
POST /api/v2/reset
GET  /api/v2/traces/*
GET  /api/v2/turns/*
```

如果浏览器没有 User Access Token，以上接口必须直接返回 `401`；页面不得再显示“默认用户”
或用 `farm_id=1` 继续请求。

### 4.2 JWT Claims

```json
{
  "iss": "farm-manager-auth",
  "aud": ["farm-manager-agent", "farm-manager-business"],
  "sub": "user-uuid",
  "type": "access",
  "role": "user",
  "farm_uid": "farm-uuid",
  "scope": "farm:read farm:write conversation:read",
  "iat": 1760000000,
  "nbf": 1760000000,
  "exp": 1760604800,
  "jti": "access-token-uuid"
}
```

强制校验字段：`iss`、`aud`、`sub`、`type`、`iat`、`exp`、`jti`。  
`farm_uid` 是租户上下文提示，不是完整授权依据；服务仍需确认 `users.id = sub`、`farms.uid = farm_uid` 和 `farms.user_id = sub` 的有效归属关系，并在内部解析出 `farm_id`。

### 4.3 签名算法

生产环境推荐使用 `RS256` 或 `EdDSA`：

- Auth 服务只保留签发私钥；
- Agent 和 Business 只保留验证公钥或 JWKS 地址；
- 通过 `kid` 支持密钥轮换；
- Agent 即使被攻破，也不能签发伪造用户 JWT。

现有 v2 使用 HS256，可作为迁移阶段方案，但必须满足：

- Business 和 Agent 共享的只是验证所需密钥；
- 不允许 Agent 使用该密钥签发用户 token；
- 生产切换到非对称签名后，废弃旧 HMAC 密钥。

## 5. Agent HTTP API 鉴权

### 5.1 适用接口

以下接口必须通过统一的 `require_user_principal` 依赖：

| 接口 | 认证 | 资源授权 |
|---|---|---|
| `POST /api/v2/chat` | User JWT | conversation 属于当前用户和农场 |
| `POST /api/v2/approve` | User JWT | turn 的 user_id/farm_id 必须匹配 |
| `GET /api/v2/turns/{turn_id}` | User JWT | turn 所属主体必须匹配 |
| `GET /api/v2/turns/{turn_id}/events` | User JWT | turn 所属主体必须匹配 |
| `POST /api/v2/turns/{turn_id}/cancel` | User JWT | turn 所属主体必须匹配 |
| `GET /api/v2/conversations` | User JWT | 仅查询当前主体数据 |
| `GET /api/v2/conversations/{id}` | User JWT | conversation 所属主体必须匹配 |
| `POST /api/v2/reset` | User JWT | 仅重置当前主体会话 |
| `GET /api/v2/traces/*` | User JWT | 仅查询当前主体或授权的管理员范围 |

健康检查、版本探活等接口可以匿名，但不得返回用户数据、配置密钥或下游详细错误。

### 5.2 鉴权行为

```text
缺少 Authorization                  → 401 unauthorized
Bearer 格式错误                     → 401 invalid_authorization
签名/算法/issuer/audience 错误       → 401 invalid_token
过期或尚未生效                       → 401 token_expired/token_not_active
用户不存在或已禁用                   → 401/403 user_inactive
farm_uid 不属于用户                  → 403 farm_forbidden
conversation/turn 不属于主体        → 403 resource_forbidden
```

Agent 认证失败时，不能创建 turn、写入会话、调用 MCP 或生成 SSE 业务事件。

## 6. Agent → Business MCP 服务间鉴权

### 6.1 请求头协议

Agent 每次创建 Business MCP session 或调用 MCP 工具时携带：

```http
Authorization: Bearer <service-token>
X-Delegation-Token: <delegation-jwt>
X-Request-Id: <request-id>
X-Trace-Id: <trace-id>
X-Turn-Id: <turn-id>
```

以下 Header 仅允许作为兼容期观测字段，不能作为 Business 的可信来源：

```http
X-User-Id: ...
X-Farm-Id: ...
X-Agent-Token: ...
```

兼容期如果仍保留它们，Business 必须校验它们与 Delegation Token 完全一致；不一致直接返回 `403 identity_mismatch`。

### 6.2 Service Token

Service Token 证明调用方是 Agent 服务，不证明具体用户：

```json
{
  "iss": "farm-manager-auth",
  "aud": "farm-manager-business-mcp",
  "sub": "agent",
  "type": "service",
  "scope": "mcp:invoke",
  "iat": 1760000000,
  "exp": 1760000900,
  "jti": "service-token-uuid"
}
```

Business 必须校验：

- 签名和允许算法；
- `iss`、`aud`、`type`；
- `sub=agent`；
- `scope` 包含 `mcp:invoke`；
- `exp`、`nbf`、时钟偏差；
- 令牌未被吊销（若启用 jti 黑名单）。

#### v2 当前迁移实现

当前 v2 代码先采用可轮换的 opaque Service Token：Agent 在
`Authorization: Bearer <AGENT_SERVICE_TOKEN>` 中携带共享服务凭证，Business
使用常量时间比较验证它；该凭证只证明调用方是 Agent，不包含用户身份，也不能替代
Delegation Token。这样可以先建立 MCP 服务边界，同时避免把 Agent JWT 私钥放入业务服务。

本节上面的 JWT Service Token 是目标形态，后续切换到 RS256/EdDSA + JWKS 时，保持请求头和
`scope=mcp:invoke` 语义不变，只替换凭证验证器。无论采用哪种形态，缺少服务凭证都必须返回
`401 mcp_auth_failed`，不能降级为匿名 MCP 调用。

### 6.3 Delegation Token

Delegation Token 由 Agent 在成功验证 User Access Token 后生成，表示 Agent 代表用户执行一次受限请求：

```json
{
  "iss": "farm-manager-agent",
  "aud": "farm-manager-business-mcp",
  "sub": "user-uuid",
  "act": {"sub": "agent", "type": "service"},
  "type": "delegation",
  "farm_uid": "farm-uuid",
  "role": "user",
  "scope": "farm:read",
  "source_jti": "user-access-token-jti",
  "conversation_id": "conversation-uuid",
  "turn_id": "turn-uuid",
  "iat": 1760000000,
  "exp": 1760000300,
  "jti": "delegation-token-uuid"
}
```

Business 必须校验：

1. Delegation Token 的签名来自受信任的 Agent 公钥。
2. `iss`、`aud`、`type`、`act` 正确。
3. `farm_uid`、`sub`、`scope` 与当前 MCP 工具所需权限一致，并解析出唯一内部 `farm_id`。
4. `source_jti` 存在且对应的用户 JWT 已由 Agent 成功校验。
5. `conversation_id`、`turn_id` 与请求头一致；缺失或不一致时拒绝。
6. 查询数据库确认用户仍为 active，且仍然拥有该农场访问权。

### 6.4 MCP 工具授权

服务认证成功不等于所有工具都可调用。每个 MCP 工具必须声明最小 scope：

| 工具类型 | 需要的 scope | 是否需要用户委托 |
|---|---|---|
| 城市搜索、公开位置查询 | `location:search` | 可选，但仍需 Service Token |
| 农场、种植、财务查询 | `farm:read` | 必须 |
| 创建/更新/删除业务数据 | `farm:write` | 必须，且继续执行 HITL |
| 管理员工具 | `admin:*` | 必须，且主体 role 必须为 admin |

`X-Farm-Id` 不再决定查询范围。工具从已验证的 Principal 读取内部 `farm_id`，并将该值传入 Service 层；对外请求上下文统一使用 `farm_uid`。

## 7. Business REST 鉴权

Business REST 直接面向 Web/Mobile 时使用 User Access Token：

```text
Authorization: Bearer <user-access-token>
```

Business REST 不接受：

- 只有 `X-Farm-Id` 的请求；
- 只有 `X-User-Id` 的请求；
- Agent Service Token 访问用户 REST 资源；
- 客户端自提交的 farm_id 覆盖 JWT 或数据库归属关系。

请求中的路径 farm、query farm 和 body farm 字段只能作为待校验输入。最终租户范围必须来自已验证 Principal；发现不一致时返回 `403 farm_forbidden`。如果 REST 需要暴露农场标识，优先使用 `farm_uid`，不要让客户端依赖自增 `farm_id`。

## 8. 农场归属与管理员权限

### 8.1 普通用户

普通用户只能访问其有效关联农场。JWT 中的 `farm_uid` 不是永久授权，用户换农场、被移除或被禁用后，Business 必须拒绝旧 token 的访问，或通过短 token/版本号机制尽快失效。

### 8.2 管理员模拟用户

管理员模拟访问必须使用显式的委托字段，不得覆盖原始 `sub`：

```json
{
  "sub": "target-user-uuid",
  "act": {"sub": "admin-user-uuid", "type": "user"},
  "role": "user",
  "farm_uid": "farm-uuid",
  "scope": "admin:impersonate farm:read"
}
```

每次模拟访问必须记录：管理员 ID、目标用户 ID、目标农场、原因、request_id、turn_id 和操作结果。没有 `admin:impersonate` 不得模拟。

## 9. 配置与密钥管理

生产配置不得把密钥提交在 `config.yaml`。建议配置如下：

```yaml
auth:
  jwt_algorithm: "RS256"
  user_jwt_issuer: "farm-manager-auth"
  user_jwt_audience:
    - "farm-manager-agent"
    - "farm-manager-business"
  user_jwt_jwks_url: "${AUTH_JWKS_URL}"

  service_token_issuer: "farm-manager-auth"
  service_token_audience: "farm-manager-business-mcp"
  service_token_jwks_url: "${AUTH_JWKS_URL}"

  delegation_issuer: "farm-manager-agent"
  delegation_audience: "farm-manager-business-mcp"
  delegation_private_key_file: "${AGENT_DELEGATION_PRIVATE_KEY_FILE}"
  delegation_public_key_file: "${AGENT_DELEGATION_PUBLIC_KEY_FILE}"
```

密钥要求：

- 用户 JWT 签发私钥只在 Auth/Business 登录签发组件可用。
- Agent 只持有自己的 Delegation 私钥和 User JWT 验证公钥。
- Business 持有 User JWT 验证公钥、Service Token 验证公钥、Agent Delegation 验证公钥。
- 密钥使用 `kid` 标识，轮换期间同时信任 old/new 两把公钥。
- 日志禁止输出 Authorization、JWT 原文、私钥、数据库连接串和第三方 API Key。

## 10. 统一错误响应

所有鉴权错误使用统一结构：

```json
{
  "detail": {
    "code": "invalid_token",
    "message": "认证令牌无效",
    "request_id": "request-uuid"
  }
}
```

建议错误码：

| code | HTTP | 说明 |
|---|---:|---|
| `missing_authorization` | 401 | 未提供 Authorization |
| `invalid_authorization` | 401 | Bearer 格式错误 |
| `invalid_token` | 401 | 签名、算法、issuer 或 audience 错误 |
| `token_expired` | 401 | 令牌已过期 |
| `user_inactive` | 403 | 用户不存在、被禁用或状态无效 |
| `farm_forbidden` | 403 | 用户无权访问该农场 |
| `service_unauthorized` | 401 | Agent 服务凭证无效 |
| `delegation_invalid` | 401 | 用户委托凭证无效 |
| `delegation_expired` | 401 | 用户委托凭证过期 |
| `identity_mismatch` | 403 | Header、委托令牌和资源身份不一致 |
| `scope_forbidden` | 403 | 当前身份没有工具或资源所需权限 |
| `resource_forbidden` | 403 | 无权访问指定 turn/conversation |
| `replay_detected` | 401 | 检测到不可重复使用的委托凭证 |

错误响应不得泄露“用户是否存在”“农场是否存在”之外的敏感内部信息；登录接口可根据产品安全策略统一返回账号或密码错误。

## 11. 迁移方案

### 阶段 0：修复当前风险

1. Agent JWT 解析失败立即返回 401，不再返回 `default_farm_id`。
2. 缺少 `JWT_SECRET`、Service Token 或 Agent Delegation 密钥时，Agent 启动失败或明确进入仅健康检查模式。
3. Business MCP 在入口校验 Service Token；无有效服务身份不得执行任何工具。
4. 暂时保留 `X-User-Id`、`X-Farm-Id`，但只用于一致性检查和迁移日志。

### 阶段 1：统一 User JWT

1. 统一登录响应为：

   ```json
   {
     "access_token": "<jwt>",
     "token_type": "Bearer",
     "user": {"id": "user-uuid", "phone": "...", "role": "user"},
     "farm_uid": "farm-uuid"
   }
   ```

2. Agent 和 Business 使用同一套 claims、issuer、audience 和错误码。
3. 所有 Agent 路由改用统一 Principal 依赖。

### 阶段 2：启用 Service Token + Delegation Token

1. Agent 使用可轮换的 opaque Service Token 建立 MCP 连接；后续再升级为 JWT Service Token。
2. Agent 为每个 turn 生成短时 Delegation Token。
3. Business 从 Delegation Token 构造 Principal，不再信任用户 Header。
4. MCP 工具增加 scope 声明和写操作权限检查。

### 阶段 3：删除兼容 Header

满足以下条件后删除 `X-Agent-Token`、`X-User-Id`、`X-Farm-Id` 的信任逻辑：

- Agent、Business、admin-web、mobile-app 全部使用新协议；
- 真实 MCP 联调中没有旧 Header-only 请求；
- 认证失败、农场越权、委托不一致测试全部通过；
- 日志和 Trace 已能记录 `actor_service`、`subject_id`、`farm_id`。

## 12. 验收标准

### 用户鉴权

- 缺少 Authorization 的 Agent `/chat` 返回 401，Redis/Mongo 不产生 turn。
- 签名错误、过期、错误 audience、错误 issuer、错误算法均返回 401。
- JWT 校验失败时不会回退到默认用户或默认农场。
- 用户访问其他用户的 conversation、turn、trace 返回 403。
- JWT 中 farm_uid 与数据库归属不一致返回 403。
- 用户被禁用后不能新建 turn，也不能执行 Business REST 写操作。

### 服务间鉴权

- 没有 Service Token 的 MCP 请求返回 401。
- Service Token audience、issuer、scope 错误返回 401/403。
- Delegation Token 的 user、farm_uid、turn、conversation 与请求不一致返回 403。
- 仅伪造 `X-User-Id` 或 `X-Farm-Id` 不能访问其他农场。
- Delegation Token 过期、重复使用或签名错误不能调用工具。
- `farm:write` 调用仍必须经过 HITL，鉴权成功不能绕过审批。
- Business 日志能够关联 `request_id`、`trace_id`、`turn_id`、`actor_service`、`subject_id` 和 `farm_id`，但不记录 token 原文。

### 真实链路

至少完成以下真实验收：

```text
登录 → 获取 User JWT → Agent /chat → Agent MCP → Business tool → SSE 完成
登录用户 A → 使用用户 B 的 conversation/turn → 403
伪造 X-Farm-Id → Business MCP → 403
Service Token 失效 → Business MCP → 401
Delegation Token 过期 → Business MCP → 401
写操作 → HITL approve → Business commit → operation_committed
```

## 13. 结论

v2 的最终鉴权边界如下：

```text
前端 → Agent：User Access Token
前端 → Business REST：User Access Token
Agent → Business MCP：Service Token + Delegation Token
Business 业务隔离：Principal.farm_uid 解析为内部 farm_id + 数据库归属校验
写操作安全：鉴权通过后仍必须走 HITL 和幂等/审批指纹校验
```

其中最重要的约束是：`farm_uid` 只能来自已验证身份，不能来自客户端或普通 Header；`farm_id` 只能由 Business 根据已验证的 `farm_uid` 解析得到；任何认证失败都必须拒绝，不能使用默认身份继续执行。

## 14. 与当前 DDL 的对应关系

本规范不要求修改 `v2/sql/farm_manager.sql` 的用户和农场主键设计：

| 层次 | 用户标识 | 农场标识 |
|---|---|---|
| JWT / Delegation Token | `sub = users.id` | `farm_uid = farms.uid` |
| Business Principal | `user_id = users.id` | `farm_uid = farms.uid`、`farm_id = farms.id` |
| 业务 Service / SQL | `users.id` | 只使用内部 `farms.id` 外键 |

## 15. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-08-13 | 新增用户鉴权、Agent 服务鉴权、用户委托凭证、MCP 授权、迁移和验收规范 |
| 2026-08-13 | 按 `v2/sql/farm_manager.sql` 明确 `sub=users.id`、`farm_uid=farms.uid`，不新增 `user_uid` |
