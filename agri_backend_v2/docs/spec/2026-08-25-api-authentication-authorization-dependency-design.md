---
spec_id: 2026-08-25-api-authentication-authorization-dependency-design
last_updated: 2026-08-25
status: in-progress
review_target: Agent REST API、Business REST API、Business MCP、FastAPI 认证与权限依赖
---

# v2 API 认证与权限依赖落地设计

## 1. 文档目的

本文补充 [v2 用户鉴权与服务间鉴权设计](2026-08-13-authentication-and-service-authorization.md)，聚焦当前代码如何落地以下需求：

1. 不在每个 API handler 中重复声明和解析 `Authorization` Header。
2. 通过接近“注解”的方式声明接口所需权限。
3. 统一 Agent REST 和 Business REST 的用户身份注入方式。
4. 保持 Business REST、Agent REST、Business MCP 三种不同认证边界。
5. 让权限策略可测试、可生成 OpenAPI 依赖关系，并能在资源级继续校验租户归属。

本文是实现方案和评审基线。当前代码已完成第一轮 REST 权限依赖、MCP 工具权限校验和 REST 错误契约迁移；完整成功 envelope 仍单独保留为后续版本化任务。

## 1.1 当前实施结果

- `shared.roles.Permission`、角色默认权限、Token scope 交集判断和 `require_permission(...)` 已落地。
- Business/Agent 受保护 REST 路由使用依赖注入；认证、接口权限和资源归属仍分层处理。
- MCP 继续使用 Service Token + Delegation Token，并在工具执行前按集中注册表校验最小权限。
- REST 错误统一为 `detail.code/message/meta`，成功业务 JSON 字段路径保持不变；admin-web 仅增强错误解析，不迁移成功响应类型。
- 剩余工作集中在真实基础设施联调、全仓库基线问题、viewer/acting-as 评审和后续成功 envelope 迁移。

## 2. 当前实现基线

### 2.1 Business REST

Business 已有集中认证依赖 `business.api.deps.get_current_user`，负责：

- 提取并校验 User Access JWT；
- 检查用户是否存在且处于 active 状态；
- 根据 `farm_uid` 解析数据库内部 `farm_id`；
- 检查用户与农场的归属关系；
- 返回当前用户身份字典。

`get_current_admin` 在此基础上检查 `admin` 角色。当前问题不是认证逻辑完全分散，而是接口函数重复声明 `authorization: Header` 或 `Depends(get_current_user)`，并且普通角色和 scope 还没有形成完整的权限矩阵。

### 2.2 Agent REST

Agent 使用 `agent.auth.parse_identity` 解析 User Access JWT。会话、聊天、审批、重置、Turn 和 Trace 接口分别接收 `authorization` 参数，并在 handler 内调用 `parse_identity`。

Agent 当前还包含以下公开或特殊入口：

| 入口 | 认证边界 |
| --- | --- |
| `/`、`/static/*` | 首页和静态资源，可公开访问 |
| `/api/v2/auth/login` | 登录代理，可公开访问 |
| `/api/v2/health` | 健康检查，可按部署策略公开 |
| `/api/v2/dev-users` | 仅 development，生产必须 404；建议同时保留管理员限制 |
| 会话、聊天、审批、重置、Turn、Trace | User Access JWT |

### 2.3 Business MCP

Business 进程同时挂载 REST 和 MCP。MCP 使用独立的：

- Agent Service Token，证明调用服务是 Agent；
- Delegation Token，证明 Agent 代表哪个用户、农场和 Turn；
- `McpAuthMiddleware`，在请求上下文注入已验证 Principal。

因此不能用一个不区分路径和凭证类型的全局认证中间件覆盖整个 Business 进程。

## 3. 评审结论

### 3.1 认证和授权分层

采用以下三层结构：

```text
凭证提取与身份认证
    -> get_current_principal

接口级粗粒度授权
    -> require_permission(Permission.X)

资源级归属和状态校验
    -> conversation / turn / farm / entity scope check
```

三层职责不可互相替代：

- 认证回答“请求来自谁”；
- 接口权限回答“这个主体能否调用这类操作”；
- 资源校验回答“这个主体能否访问请求中的具体对象”。

### 3.2 不采用无条件的全局 ASGI 认证中间件

不建议在 Agent 或 Business 的最外层统一拦截所有请求，原因如下：

1. Agent 有登录、健康检查、静态资源和开发辅助入口等公开例外。
2. Business `/api/v2` 使用 User Access JWT，而 `/mcp` 使用 Service Token + Delegation Token。
3. ASGI 中间件无法自然表达每个接口的具体权限，也不利于 FastAPI OpenAPI 和依赖 override。
4. 中间件成功后仍需要把 Principal 注入业务函数，最终仍然需要额外的上下文约定。

统一认证器应存在，但实现为各服务内部的 FastAPI 依赖，而不是一个跨所有协议的无条件中间件。

### 3.3 不采用普通 Python 权限装饰器作为主机制

不把以下形式作为主方案：

```python
@requires("farm:write")
```

普通装饰器需要额外实现自定义 `APIRoute`、元数据扫描或签名保留，否则容易影响 FastAPI 参数注入、OpenAPI、异步 handler、SSE StreamingResponse 和测试替换。

使用 FastAPI 原生依赖工厂和 `Annotated` 类型别名，可以得到相同的声明式体验，同时保留框架能力。

## 4. 统一权限模型

### 4.1 权限不是角色的同义词

`UserRole` 继续表示主体类别；`Permission` 表示具体操作能力。

建议在 `shared/roles.py` 或同一 shared 授权模块中增加以下稳定枚举：

```python
class Permission(str, Enum):
    AGENT_INVOKE = "agent:invoke"
    CONVERSATION_READ = "conversation:read"
    CONVERSATION_WRITE = "conversation:write"
    TURN_APPROVE = "turn:approve"
    TURN_CANCEL = "turn:cancel"
    TRACE_READ = "trace:read"
    TRACE_DEBUG = "trace:debug"
    FARM_READ = "farm:read"
    FARM_WRITE = "farm:write"
    LOCATION_SEARCH = "location:search"
    PROFILE_READ = "profile:read"
    PROFILE_WRITE = "profile:write"
    ADMIN_USER_READ = "admin:user:read"
    ADMIN_USER_WRITE = "admin:user:write"
    ADMIN_DEBUG = "admin:debug"
```

权限枚举和角色默认权限应是纯数据和纯函数，不应依赖 FastAPI、数据库或请求对象。

### 4.2 角色默认权限

第一阶段不新增数据库角色，沿用现有 `admin/user/dev`，避免把 API 权限改造和用户模型迁移绑定在一起：

| 角色 | 默认权限原则 |
| --- | --- |
| `user` | Agent 使用、会话读写、Trace 自身范围、农场业务读写 |
| `dev` | 与 `user` 相同，不自动获得管理员权限；仅 development 辅助能力可见 |
| `admin` | 普通业务权限加用户管理、管理员调试和受控模拟能力 |

`dev` 不能通过角色名称、前端选择或 `/dev-users` 自动获得 `admin` 权限。

### 4.3 有效权限计算

权限判断应基于：

```text
effective_permissions
    = role_permissions(current_role)
      ∩ token_scopes
      ∩ protocol_capabilities
```

说明：

- 角色权限来自当前可信主体角色；
- token scope 是令牌签发时的能力上限；
- 协议能力限制当前入口，例如 MCP 还必须具备 `mcp:invoke` 和有效委托；
- 任何一层缺失都应拒绝，不能通过角色自动扩大 token 已声明的权限。

Business MCP 的主体角色应以数据库当前角色为准，Delegation Token 的 role 只能作为传输信息，不能绕过数据库状态。

## 5. FastAPI 依赖式实现

### 5.1 Principal 依赖

Business 和 Agent 可以分别实现协议适配，但对 handler 暴露统一概念：

```python
from typing import Annotated
from fastapi import Depends

CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
```

Business 的 `get_current_principal` 继续复用现有 `get_current_user` 的数据库和农场归属校验；Agent 的适配器负责从 Header 调用 `parse_identity`。两者不应共享包含数据库查询的实现，因为服务信任边界不同。

### 5.2 权限依赖工厂

权限检查使用依赖工厂：

```python
def require_permission(permission: Permission):
    def check(principal: CurrentPrincipal) -> Principal:
        if not principal.has_permission(permission):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "permission_denied",
                    "message": "当前身份没有所需权限",
                    "permission": permission.value,
                },
            )
        return principal

    return check
```

接口使用方式：

```python
@router.post(
    "/workers",
    dependencies=[Depends(require_permission(Permission.FARM_WRITE))],
)
def create_worker(request: WorkerRequest, user: CurrentPrincipal):
    return worker_service.create(user["farm_id"], request)
```

当 handler 需要身份时使用 `CurrentPrincipal`；只需要权限、不需要读取身份时使用路由级 `dependencies`。FastAPI 会缓存同一请求中的相同依赖，认证不会因同时声明权限依赖和 Principal 参数而重复执行。

### 5.3 路由级和接口级依赖的使用边界

| 场景 | 推荐方式 |
| --- | --- |
| 一个完整 router 的所有接口都必须登录 | router/include_router 级 `Depends(get_current_principal)` |
| 同一 router 内不同接口权限不同 | 单个 route 的 `dependencies=[Depends(require_permission(...))]` |
| handler 需要 user_id、farm_id | `CurrentPrincipal` 参数 |
| 只需管理员角色 | `require_permission(ADMIN_...)`，不再散落 `is_admin_role` |
| 具体会话、Turn、农场对象归属 | 保留 service 或局部资源校验函数 |

路由级认证依赖只能减少认证重复，不能替代接口级权限，也不能替代资源归属检查。

## 6. Agent API 权限矩阵

| API 范围 | 建议权限 | 额外校验 |
| --- | --- | --- |
| `POST /chat` | `agent:invoke` | conversation scope、HITL 和写工具策略 |
| `GET /conversations*` | `conversation:read` | 当前用户和农场范围 |
| `POST /reset` | `conversation:write` | 当前用户和 conversation scope |
| `POST /approve` | `turn:approve` | Turn 所属用户、状态和审批阶段 |
| `GET /turns*` | `conversation:read` | Turn 所属用户和农场 |
| `POST /turns/{id}/cancel` | `turn:cancel` | Turn 所属用户和可取消状态 |
| `GET /traces*` | `trace:read` | 默认只允许主体自身范围 |
| `admin_debug` SSE/Trace 投影 | `admin:debug` | viewer 身份单独校验，不能只看 execution 身份 |

`X-Viewer-Authorization` 代表查看者，不应覆盖执行主体；管理员调试权限必须由 viewer Principal 单独确认。

## 7. Business REST 权限矩阵

| API 范围 | 建议权限 |
| --- | --- |
| Dashboard、农场、作物、工人、成本、债务、天气查询 | `farm:read` |
| 创建、修改、删除业务记录 | `farm:write` |
| 用户资料和设置读取 | `profile:read` |
| 用户资料和设置修改 | `profile:write` |
| `/admin/users` 列表和详情 | `admin:user:read` |
| `/admin/users` 创建或管理 | `admin:user:write` |
| 登录、公开注册、健康检查 | 公开或按现有兼容规则处理 |

现有 `get_current_admin` 可以迁移为 `require_permission(ADMIN_USER_READ/WRITE)` 的兼容实现；迁移完成前，两者可以并存，但新增接口不再直接判断 role 字符串。

## 8. Business MCP 工具授权

### 8.1 Middleware 只负责协议认证

`McpAuthMiddleware` 继续负责：

1. Service Token 校验；
2. Delegation Token 校验；
3. `sub`、`farm_uid`、Turn 和 Header 一致性校验；
4. 数据库用户状态和农场归属校验；
5. 向请求上下文注入 Principal。

它不应仅因为请求已经通过认证，就允许所有 MCP 工具调用。

### 8.2 工具权限声明

每个 MCP 工具必须有最小权限声明：

| 工具类型 | 最小权限 | 委托要求 |
| --- | --- | --- |
| 城市和位置搜索 | `location:search` | Service Token；是否需要用户委托按工具定义 |
| 农场、种植、财务查询 | `farm:read` | 必须有用户委托 |
| 创建、修改、删除业务数据 | `farm:write` | 必须有用户委托，并继续执行 HITL |
| 管理员工具 | `admin:*` | 必须有用户委托，当前角色必须是 admin |

推荐使用工具策略注册表或保留签名的工具包装器，不建议在 ASGI middleware 中解析 JSON-RPC body 来猜测工具名。

## 9. HTTP 状态码与统一 API 返回格式

### 9.1 当前问题

Business 已有统一异常处理，但当前错误 envelope 是 `detail`；Agent 的不同 handler 同时返回字符串 detail、字典 detail 和 FastAPI 默认错误；MCP middleware 还有自己的 `error/message` 结构。客户端因此不能只依赖一个稳定的错误读取路径。

本节定义目标格式。认证授权改造不得顺便破坏已有 `/api/v2` 成功响应字段；现有接口通过兼容迁移逐步收敛，新接口和发生契约变更的接口必须直接采用目标格式。

本次实施决策：先统一 REST 错误响应和 HTTP 状态码，继续返回现有成功业务 JSON，不给所有成功响应增加 `data` 包装。这样可以保持 `admin-web` 当前 `response.data`、登录字段、分页字段和 Trace 字段路径不变；完整成功 envelope 作为后续独立 API 契约迁移，不与本次认证授权改造绑定。

### 9.2 JSON API 成功响应（后续目标）

后续如果启动完整成功 envelope 迁移，除 `204 No Content` 外，JSON API 可以统一使用：

```json
{
  "success": true,
  "code": "ok",
  "message": "请求成功",
  "data": {
    "id": "worker-1"
  },
  "meta": {
    "request_id": "req-uuid"
  }
}
```

约束：

- `success` 只表示 HTTP 请求是否成功，不表示 Agent 业务回答内容是否满足用户预期；
- `code=ok` 为默认成功码，特殊成功语义可以使用领域 code，但不得用 HTTP 200 隐藏业务失败；
- 单对象放在 `data`；列表放在 `data.items`，分页信息放在 `data.pagination`；
- `meta.request_id` 使用服务端生成或可信链路传入的请求 ID，不能把认证 token 当作请求 ID；
- `204` 不返回 body，适用于明确无响应体的删除或幂等成功操作。

列表示例：

```json
{
  "success": true,
  "code": "ok",
  "message": "请求成功",
  "data": {
    "items": [],
    "pagination": {
      "page": 1,
      "page_size": 20,
      "total": 0,
      "has_more": false,
      "next_cursor": null
    }
  },
  "meta": {
    "request_id": "req-uuid"
  }
}
```

### 9.3 JSON API 错误响应

所有 REST 错误统一使用同一层级的 `error` 对象：

```json
{
  "success": false,
  "code": "permission_denied",
  "message": "当前身份没有所需权限",
  "data": null,
  "error": {
    "code": "permission_denied",
    "message": "当前身份没有所需权限",
    "meta": {
      "permission": "farm:write",
      "path": "/api/v2/workers",
      "request_id": "req-uuid"
    }
  },
  "meta": {
    "request_id": "req-uuid"
  }
}
```

目标是让客户端可以稳定读取顶层 `success/code/message`，同时让 `error.meta` 承载错误上下文。`error.code` 和顶层 `code` 必须一致；成功响应不得包含 `error`；错误响应不得把异常 traceback、SQL、token、密码或完整认证 Header 返回给客户端。

迁移期间，如果必须兼容现有客户端，可以暂时保留 `detail` 作为兼容字段，但新代码不得同时创造 `detail`、`error`、字符串 detail 三套语义。兼容字段应由统一异常处理器生成，而不是由业务 handler 手写。

### 9.4 HTTP 状态码规则

| 情况 | 状态码 | code 示例 | 说明 |
| --- | --- | --- | --- |
| 查询、更新或幂等成功且有 body | 200 | `ok` | 返回统一成功 envelope |
| 创建资源成功 | 201 | `created` 或 `ok` | `Location` 可选；返回创建结果 |
| 异步任务已接收 | 202 | `accepted` | 只表示已接收，不表示任务完成 |
| 成功但没有 body | 204 | 无 | 不返回 JSON body |
| 请求体、路径或 query 结构错误 | 422 | `validation_error` | Pydantic/schema 校验失败 |
| 请求语义不满足业务约束 | 400 | `invalid_request` | 参数结构合法但业务表达无效 |
| 缺少或格式错误的 User JWT | 401 | `missing_authorization` / `invalid_authorization` | 客户端应重新登录或补充凭证 |
| JWT 过期或签名无效 | 401 | `token_expired` / `invalid_token` | 不得降级为匿名或默认用户 |
| 用户被禁用或农场归属失效 | 403 | `user_inactive` / `farm_forbidden` | 主体已识别但不能访问 |
| 主体没有接口权限 | 403 | `permission_denied` | 权限依赖拒绝 |
| 主体不属于目标资源 | 403 | `resource_forbidden` / `turn_forbidden` | 资源级校验拒绝 |
| 资源不存在 | 404 | `not_found` / `turn_not_found` | 不泄露不必要的存在性信息 |
| 幂等冲突、重复写入或 cursor revision 冲突 | 409 | `duplicate` / `idempotency_conflict` / `cursor_conflict` | 客户端需要读取或重新获取状态 |
| 限流、并发容量或排队拒绝 | 429 | `rate_limited` / `capacity_exceeded` | 可通过 `Retry-After` 提供重试提示 |
| 上游服务返回无效响应 | 502 | `upstream_error` | Agent、Business 或 Provider 的上游响应错误 |
| Redis、Mongo、数据库或认证配置不可用 | 503 | `dependency_unavailable` / `auth_unavailable` | 表示服务暂时不可用 |
| 未分类内部异常 | 500 | `internal` | 日志记录完整异常，客户端只收到稳定文案 |

状态码和 `code` 必须同时正确：不能用 200 表示认证失败、权限失败、参数失败或数据库故障，也不能只修改 JSON 中的 `code` 而保持错误的 HTTP 状态码。

### 9.5 Agent SSE 和 Business MCP 的协议边界

SSE 建立连接前仍使用 HTTP 状态码和 REST 错误 envelope。连接建立并发送 `200 text/event-stream` 后，不能再修改 HTTP 状态码；执行期间的失败通过统一 SSE `error` 事件表达：

```json
{
  "event": "error",
  "data": {
    "code": "tool_error",
    "message": "工具执行失败",
    "retryable": false,
    "request_id": "req-uuid"
  }
}
```

SSE error 之后仍必须发送唯一终态 `done`，客户端不能把 SSE 传输成功误判为 Agent 业务成功。

MCP 受 JSON-RPC/Streamable HTTP 协议约束，不强行套 REST 的 `success/data` 成功 envelope；但 middleware 和工具错误必须至少稳定提供 `code`、`message`、`request_id`，并沿用本节的 HTTP 状态码语义：认证失败 401、身份或权限不满足 403、依赖不可用 503。

### 9.6 统一异常处理器职责

Business 和 Agent 都应安装同一语义的异常处理器：

1. 捕获 `HTTPException`，把 status、detail 和异常上下文转换为统一 error envelope；
2. 捕获 `RequestValidationError`，统一返回 422 `validation_error`；
3. 捕获未处理异常，记录完整结构化日志并返回 500 `internal`；
4. 注入 `request_id`、path、服务名和必要的领域元数据；
5. 不在 handler 中拼接最终错误 JSON。

Agent 当前缺少与 Business 对等的应用级异常处理器，应在 Agent API 迁移权限依赖时一并补齐。MCP 仍保留自己的 transport error handler，但字段语义必须与 REST 对齐。

### 9.7 admin-web 兼容策略和 HTTP 契约文件

当前 `admin-web/src/api/client.ts` 负责 token 注入、401 跳转和错误提示；大多数 `admin-web/src/api/*.ts` 和少量页面直接使用 `response.data`，领域 API 方法的 TypeScript 泛型也直接写成 `User`、`PaginatedList<T>`、`TraceTimelineResponse` 等业务结果类型。

因此，后端一次性把所有成功响应从：

```json
{
  "id": "worker-1"
}
```

改成：

```json
{
  "success": true,
  "code": "ok",
  "message": "请求成功",
  "data": {
    "id": "worker-1"
  },
  "meta": {}
}
```

如果没有前端兼容层，会导致以下连锁修改：

- 所有 `res.data` 需要改成 `res.data.data`；
- 所有 endpoint 泛型需要从 `Foo` 改成 `ApiSuccess<Foo>`；
- 列表、分页和 Trace 聚合的字段路径需要批量调整；
- 登录、用户切换、401 拦截、测试 fixture 和页面 mock 需要同步修改；
- 页面层可能同时出现新旧 envelope 判断，形成重复兼容逻辑。

本文不建议在本次实施中一次性改动页面层。后续如果启动完整 envelope 迁移，建议在 `admin-web/src/api/` 增加一个传输契约文件，例如 `http-contract.ts`，集中管理：

```ts
export const HTTP_STATUS = {
  OK: 200,
  CREATED: 201,
  ACCEPTED: 202,
  NO_CONTENT: 204,
  BAD_REQUEST: 400,
  UNAUTHORIZED: 401,
  FORBIDDEN: 403,
  NOT_FOUND: 404,
  CONFLICT: 409,
  UNPROCESSABLE_ENTITY: 422,
  TOO_MANY_REQUESTS: 429,
  BAD_GATEWAY: 502,
  SERVICE_UNAVAILABLE: 503,
  INTERNAL_SERVER_ERROR: 500,
} as const;

export interface ApiMeta {
  request_id?: string;
  path?: string;
  [key: string]: unknown;
}

export interface ApiSuccess<T> {
  success: true;
  code: string;
  message: string;
  data: T;
  meta?: ApiMeta;
}

export interface ApiError {
  success: false;
  code: string;
  message: string;
  data: null;
  error: {
    code: string;
    message: string;
    meta?: ApiMeta;
  };
  meta?: ApiMeta;
}

export type ApiEnvelope<T> = ApiSuccess<T> | ApiError;
```

文件职责边界：

| 文件 | 职责 |
| --- | --- |
| `src/api/http-contract.ts` | HTTP 状态码、成功/错误 envelope、错误码类型守卫和兼容解包函数 |
| `src/api/client.ts` | Axios 实例、token 注入、统一错误提示、401 跳转和响应适配 |
| `src/api/users.ts`、`src/api/crops.ts` 等 | 领域响应类型和 endpoint 函数，不定义 HTTP 状态码 |
| 页面组件 | 只消费领域结果和统一错误，不判断 `response.data.data` |

后续 envelope 迁移方式：

1. `client.ts` 先识别新 envelope，成功时集中解包 `data`，旧的裸业务响应原样放行。
2. `client.ts` 的错误读取同时兼容新 `error.message`、旧 `detail.message` 和历史字符串 detail；兼容逻辑只保留在这一层。
3. 先迁移登录、用户、列表和高风险写接口，页面调用保持原来的领域结果类型。
4. 后端接口全部完成迁移并删除旧响应后，再收紧 `ApiEnvelope<T>` 类型，禁止裸响应。
5. SSE 不进入 Axios JSON 解包器，继续使用独立的 SSE event contract。

本次实际实施不新增前端文件，也不要求页面层改动；后端只使用 shared REST 错误契约文件，并保持成功响应结构。后续若采用前端 client adapter，影响主要集中在 `client.ts`、`http-contract.ts` 和少量 API contract 测试，页面层不需要同步重写。只有在要求 TypeScript 从编译期强制所有接口都返回 envelope 时，才需要批量改造各 API 模块的 Axios 泛型和 fixture；这应作为后续独立迁移。

### 9.8 统一返回格式的版本和兼容规则

统一 envelope 是 API 契约变更，不应只修改后端异常处理器而不更新客户端契约。采用以下规则：

- 本次新增或修改的 REST 接口保持现有成功业务 JSON，错误统一使用 `detail.code/detail.message/detail.meta`；
- 后端状态码、错误码、错误 detail 构造和 Agent/Business 异常处理器集中在 `shared/api_response.py`；
- 后续若启动完整成功 envelope，已被 `admin-web` 使用的旧接口先由前端 client adapter 兼容，再逐个切换后端响应；
- 任何响应迁移期间，服务端不得在同一个接口随机返回裸对象和 envelope；兼容期必须按明确的接口版本、请求头或服务端固定策略决定格式；
- 后端删除旧格式前，必须完成 admin-web API 模块、页面、测试 fixture 和移动端调用方的检索；
- 登录响应、分页列表、Trace 查询和 Agent Chat 是高风险迁移对象，应有独立契约测试；
- REST JSON、SSE 和 MCP 分别维护 transport contract，不使用一个 TypeScript 类型覆盖三种协议。

## 10. 分阶段迁移计划

### Phase 0：冻结策略

- 评审并冻结 `Permission` 命名和角色默认权限。
- 明确 `dev` 仍是普通用户权限。
- 明确 Trace、管理员调试、模拟用户的 viewer/acting-as 边界。
- 不改变现有 JWT Header 和 `/api/v2` 路径。

### Phase 1：增加纯策略和依赖适配器

- 增加权限枚举、角色权限矩阵、scope 解析和 `has_permission`。
- 增加 Business `CurrentPrincipal` 和权限依赖工厂。
- 增加 Agent `get_current_principal`，内部适配 `parse_identity`。
- 在后续成功 envelope 迁移阶段，再增加 admin-web `http-contract.ts` 和 client adapter；本次不修改前端。
- 为权限函数、缺失 scope、未知权限、admin/dev 边界增加单元测试。

### Phase 2：迁移 Business REST

- 先迁移 `/admin/users` 和高风险写接口。
- 再迁移普通读接口和用户资料接口。
- 删除新代码中的直接 role 字符串判断。
- 保留 `get_current_admin` 作为兼容别名，确认无调用方后再删除。

### Phase 3：迁移 Agent REST

- 将受保护 endpoint 移到 protected router 或增加路由级认证依赖。
- handler 改为接收 `CurrentPrincipal`，不再直接接收 `authorization`。
- 将 conversation、Turn、Trace 和 admin debug 权限分别接入。
- 保留资源级 `_check_turn_scope` 等校验。

### Phase 4：补齐 MCP 工具授权

- 建立工具名到最小权限的注册表。
- 在实际工具执行前校验 Principal 的有效权限。
- 对查询、写入、管理员工具分别增加 403 测试。
- 验证 Service Token 认证通过但用户 scope 不足时仍然拒绝。

### Phase 5：清理和文档同步

- 搜索并清理生产 API 中直接解析 Header 的重复逻辑。
- 更新 API reference、认证设计和安全规则。
- 完成 admin-web 领域 API 的 envelope 迁移后，删除旧裸响应兼容分支。
- 执行架构约束、复杂度、lint、文档新鲜度和聚焦测试。

## 11. 验收标准

### 11.1 API 行为

- 本次改造的成功 JSON API 保持现有业务 JSON 字段结构；`204` 无 body。完整 `success/code/message/data/meta` envelope 另行立项。
- 本次改造的 REST 错误统一返回兼容外层 `detail`，并在其中提供稳定的 `code/message/meta`。
- 422 只用于结构校验错误，400 用于结构合法但业务语义无效的请求。
- 无 User JWT 访问受保护 Agent/Business REST 返回 401。
- 有效 User JWT 但缺少权限返回 403 `permission_denied`。
- `dev` 不能访问管理员用户管理和管理员调试接口。
- admin 访问管理员接口成功，但仍必须满足资源级归属或显式模拟规则。
- 不同用户访问同一 conversation、Turn、farm 资源仍被资源级校验拒绝。
- `/auth/login`、健康检查和静态首页不被错误的全局 User JWT 依赖拦截。

### 11.2 MCP 行为

- 缺少 Service Token 或 Delegation Token 时拒绝请求。
- MCP 认证通过但工具所需 scope 不足时返回权限错误。
- Delegation Token 中的用户或农场与数据库当前归属不一致时拒绝。
- 写工具仍必须经过既有 HITL 和幂等约束。

### 11.3 工程质量

- 权限策略可以脱离 FastAPI 单元测试。
- OpenAPI 能显示受保护路由的依赖边界。
- FastAPI dependency override 可以注入测试 Principal。
- Agent 和 Business 的 REST 异常处理器对同一错误产生相同状态码和 envelope。
- SSE 建连前使用 HTTP 错误，建连后使用 `error` 事件并最终发送唯一 `done`。
- 本次改造不要求 admin-web 页面解析新的成功 envelope；现有错误读取保持 `detail` 兼容，后续 envelope 迁移再集中到 `src/api/http-contract.ts` 与 `client.ts`。
- 当前兼容测试覆盖 REST 错误状态码和 detail 结构；完整 envelope 的登录、分页、Trace 迁移测试属于后续独立任务。
- 认证 Header、token、密码和 Delegation Token 不进入普通日志或响应。
- 代码迁移后通过新增代码测试、lint、架构约束和复杂度预算检查。

## 12. 待评审问题

1. 第一阶段是否接受新增 `Permission` 枚举，但暂不增加数据库角色和用户权限表？本文建议接受。
2. 普通用户是否允许查看自身 Trace 的完整工具参数？本文建议继续使用脱敏后的 `trace:read` 投影。
3. `/api/v2/dev-users` 在 development 是否还需要 admin JWT？本文建议保留 loopback/development 限制，并增加 admin 限制；最终以实际 Playground 使用方式为准。
4. MCP 工具权限声明最终放在工具注册表、Skill metadata，还是 FastMCP 工具包装器？本文建议先使用集中注册表，避免依赖具体 FastMCP 装饰器扩展能力。
5. 是否需要 `admin:impersonate` 独立权限和审计事件？如果管理员模拟用户用于生产运营，应独立建模，不能复用 `admin:debug`。
6. 现有 `/api/v2` 直接返回业务对象的接口，是否通过兼容字段逐步迁移到 `data` envelope？本文建议不在权限改造中一次性破坏现有客户端契约。

## 13. 关联文档

- [实施待办清单](2026-08-25-api-authentication-authorization-dependency-design-todos.md)
- `2026-08-13-authentication-and-service-authorization.md`
- `2026-08-21-agent-sse-execution-event-contract-proposal.md`
- `2026-08-23-agent-conversation-history-query-engineering-plan.md`
- `../reference/agent_sse_design_methodology.md`
