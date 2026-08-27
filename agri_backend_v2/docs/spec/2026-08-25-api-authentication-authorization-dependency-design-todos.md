# v2 API 认证与权限依赖实施待办清单

> 生成时间：2026-08-25
> 来源文档：[2026-08-25-api-authentication-authorization-dependency-design.md](2026-08-25-api-authentication-authorization-dependency-design.md)
> 实施分支：`codex/api-auth-response-contract`
> 当前状态：进行中

## 使用说明

- `[x]` 表示已经完成并有测试或代码证据。
- `[ ]` 表示尚未完成，完成后需要补充对应测试和验证结果。
- 本次改造先统一 REST 错误响应和 HTTP 状态码，保持现有成功业务 JSON 不变，避免 `admin-web` 大规模重构。
- 完整 `success/code/message/data/meta` 成功 envelope 是后续独立迁移，不作为本次认证授权改造的完成条件。

## Phase 0：冻结边界和权限策略

- [x] 确认 Agent REST、Business REST、Business MCP 使用不同凭证边界。
- [x] 确认不使用无条件的全局 ASGI User JWT 认证中间件。
- [x] 确认使用 FastAPI 原生依赖工厂和 `Annotated` 表达接口权限。
- [x] 确认当前阶段保持成功响应字段路径不变，错误统一走 `detail.code/detail.message/detail.meta`。
- [x] 冻结 `Permission` 枚举名称和命名空间。
  - [x] 固化 `agent:*`、`conversation:*`、`turn:*`、`trace:*`、`farm:*`、`profile:*`、`admin:*`、`location:*` 权限值。
  - [x] 确认权限值属于稳定 API 契约，后续不使用散落字符串替代。
- [x] 冻结 `user`、`dev`、`admin` 的默认权限矩阵。
  - [x] 确认 `dev` 不自动获得管理员权限。
  - [x] 确认 `/api/v2/dev-users` 在 development 外返回 404；loopback/admin 限制仍待评审，不在本轮强制改变静态 Agent Playground。
- [x] 冻结 viewer、acting-as 和 execution identity 的边界：execution identity 来自当前 User JWT，viewer 只用于额外的管理员诊断投影，acting-as 不在本轮开放。
  - [x] 确认 `X-Viewer-Authorization` 只代表查看者。
  - [ ] 评审是否新增独立的 `admin:impersonate` 权限和审计事件。

## Phase 1：共享认证授权策略和 REST 响应契约

### 1.1 已完成的响应契约基础

- [x] 新增 `shared/api_response.py`，集中管理 HTTP 状态码、错误码映射和错误 detail 构造。
- [x] 统一 `HTTPException`、请求校验异常和未处理异常的 REST 错误结构。
- [x] 错误结构保留 `detail` 外层，兼容现有客户端读取方式，并统一内部的 `code/message/meta`。
- [x] 错误 `meta` 注入 `path` 和可信 `X-Request-ID`，不回传认证 Header、token、密码或 traceback。
- [x] Agent 和 Business 安装同一语义的应用级异常处理器。
- [x] 增加状态码、422 校验错误、500 脱敏错误和旧/新 HTTP 异常 detail 的 focused tests。
- [x] 保持现有成功 JSON 结构，未要求 `admin-web` 修改 `response.data`、登录字段、分页字段和 Trace 字段路径。

### 1.2 待实施的共享授权能力

- [x] 在 `shared/roles.py` 或清晰边界的 shared 授权模块中增加 `Permission` 枚举。
- [x] 增加纯函数 `role_permissions(role)`、`scope_permissions(scopes)` 和 `has_permission(...)`。
  - [x] 未知角色、未知权限和缺失 scope 默认拒绝。
  - [x] 有效权限遵循角色权限、token scope、协议能力的交集。
  - [x] 纯策略函数不依赖 FastAPI、数据库、请求对象或日志副作用。
- [x] 明确 `Principal` 的最小字段和统一能力接口。
  - [x] 至少覆盖 `user_id`、`role`、`farm_id/farm_uid`、`scope`、`token_id`。
  - [x] 兼容现有 Agent identity 字典和 Business current user 字典，迁移期间不强制一次性改完所有调用方。
- [x] 增加权限策略单元测试。
  - [x] user、dev、admin 默认权限。
  - [x] scope 缺失、scope 缩小权限和未知权限。
  - [ ] inactive 用户、失效农场和无效 delegation 的拒绝行为。

## Phase 2：Business REST 依赖迁移

- [x] 实现 Business `get_current_principal`，复用现有 User JWT、用户状态、`farm_uid` 和农场归属校验。
- [x] 实现 Business `CurrentPrincipal` 类型别名和 `require_permission(permission)` 依赖工厂。
- [x] 保留 `get_current_user`、`get_current_admin` 作为兼容入口，已迁移接口不再直接判断 role 字符串。
- [x] 盘点并迁移第一批 Business 路由权限矩阵。
  - [ ] 公开登录、公开注册和健康检查不挂 User JWT 依赖。
  - [ ] Dashboard、农场、作物、工人、成本、债务、天气查询使用 `farm:read`。
  - [x] 业务创建、修改、删除使用 `farm:write`（已迁移农场和工人接口）。
  - [x] 用户资料读写分别使用 `profile:read`、`profile:write`。
  - [x] `/admin/users` 列表/详情使用 `admin:user:read`，创建/管理使用 `admin:user:write`。
- [x] 优先迁移 `/admin/users` 和第一批高风险写接口。
- [x] 保留 service 层的 farm/resource ownership 校验，不把接口权限当作资源归属校验的替代品。
- [x] 完成 Business 普通读写路由迁移（作物、成本、债务、作业单、农事日志、天气和 Dashboard）。
- [x] 增加 Business 路由测试。
  - [x] 无 token、无效 token、过期 token 返回 401。
  - [x] 有效身份但缺少权限返回 403 `permission_denied`。
  - [x] dev 访问 admin 接口被拒绝，admin 在合法范围内成功。
  - [x] 不同用户访问其他 farm 或业务资源仍被资源级校验拒绝。
  - [x] 原有成功响应字段保持兼容。

## Phase 3：Agent REST 依赖迁移

- [x] 实现 Agent `get_current_principal`，内部适配 `agent.auth.parse_identity`。
- [x] 实现 Agent `CurrentPrincipal` 和 `require_permission(permission)`，不改变现有 User JWT Header 和 `/api/v2` 路径。
- [x] 将受保护路由纳入 protected route-level permission dependencies。
- [x] 生产 handler 已改为复用注入的 Principal；旧直接调用测试保留兼容解析路径。
- [x] 按权限迁移 Agent 接口。
  - [x] `POST /chat` 使用 `agent:invoke`，保留 conversation scope、HITL 和写工具策略。
  - [x] conversation 查询和 `GET /turns*` 使用 `conversation:read`。
  - [x] reset 使用 `conversation:write`。
  - [x] approve 使用 `turn:approve`。
  - [x] cancel 使用 `turn:cancel`。
  - [x] Trace 查询使用 `trace:read`，管理员调试投影保留单独 viewer 校验。
- [x] 保留 `_check_turn_scope` 等资源级校验，并区分 execution identity 与 viewer identity。
- [x] 明确公开入口不被受保护 router 错误拦截。
  - [x] `/`、`/static/*`、登录、health 按现有规则可访问。
  - [x] `/api/v2/dev-users` 在 development 可用、生产必须 404；admin/loopback 策略另列为评审项。
- [x] 增加 Agent REST、SSE 和回归测试。
  - [x] 权限依赖返回 403 `permission_denied`，认证错误仍由统一认证器返回 401。
  - [x] chat、conversation、approve、reset、turn、trace 路由已挂接权限依赖。
  - [x] SSE 建连前缺失/缩小 scope 的 HTTP 端到端测试。
  - [x] SSE 建连后错误仍发送 `error`，并最终发送唯一 `done`。
  - [x] 既有成功事件字段和客户端解析路径保持兼容。

## Phase 4：Business MCP 工具授权

- [x] 保持 `McpAuthMiddleware` 只负责 Service Token、Delegation Token 和主体/农场/Turn 一致性认证。
- [x] 建立 MCP 工具名到最小权限的集中注册表；保留工具 operation policy 作为未知 operation 的兼容兜底。
  - [x] 位置搜索使用 `location:search`。
  - [x] 农场、种植、财务查询使用 `farm:read`。
  - [x] 创建、修改、删除使用 `farm:write`。
  - [x] 管理员工具使用对应 `admin:*` 权限（当前尚无管理员 MCP 工具）。
- [x] 在实际工具执行前校验有效 Principal 权限，不在 ASGI middleware 中解析 JSON-RPC body 猜测工具名。
- [x] 查询工具、写工具、管理员工具分别补充真实工具成功和 403 测试；查询/写工具已有真实路径，当前无管理员 MCP 工具。
- [x] 验证 Service Token 认证上下文中的用户 scope 不足时仍然拒绝。
- [x] 验证 Delegation Token 与数据库当前用户、农场归属不一致时拒绝。
- [x] 保留写工具既有 HITL、幂等和资源归属约束。
  - [x] Agent 侧 HITL 串行审批和拒绝路径已有回归测试。
  - [x] MCP 写调用不默认重试；显式幂等写入才允许重试，并保留 farm scope 与审批指纹。
- [x] 对 MCP transport error 统一提供 `code`、`message`、`request_id`，但不强行套 REST `success/data` envelope。

## Phase 5：admin-web 兼容和后续 envelope 迁移

### 5.1 本次改造的兼容验收

- [x] 后端错误统一不改变成功响应字段路径。
- [x] 验证 `admin-web` client 对 `detail.message`、`detail.code` 和历史字符串 detail 的读取兼容性。
- [x] 增加或更新 client error parser 测试，覆盖 401、403、409、422、503。
- [x] 检查登录、用户切换、分页、Trace 和 Agent Chat 不需要修改领域 response 类型。
- [x] 明确本次不新增 `admin-web/src/api/http-contract.ts`，避免为未实施的成功 envelope 提前制造大规模类型迁移。

### 5.2 后续完整成功 envelope 迁移（不作为本次完成条件）

- [x] 已决定本轮不启动 `success/code/message/data/meta` 成功 envelope 迁移，后续另开版本化任务。
- [ ] 新增 `admin-web/src/api/http-contract.ts`，集中管理状态码、成功/错误类型和兼容解包函数。
- [ ] 在 `client.ts` 集中兼容新 envelope、旧裸响应和历史错误 detail。
- [ ] 按登录、用户、列表、高风险写接口分批迁移，并为每批增加契约测试。
- [ ] 完成所有客户端、fixture、页面和移动端调用方检索后，再删除旧裸响应兼容分支。
- [ ] REST JSON、SSE、MCP 分别维护 transport contract，不共用一个 envelope 类型。

## Phase 6：验证、文档和清理

- [x] 运行 shared API response focused tests。
- [x] 运行认证相关、Agent SSE、Agent run loop 和 MCP retry focused tests。
- [ ] 完成全仓库 Ruff check 和 format check。
  - [x] 本次修改文件已通过 focused Ruff check 和 format check。
  - [ ] 既有脚本、服务导入和历史文件的 baseline lint/format 问题仍待专项清理。
- [x] 运行架构依赖检查。
- [x] 运行 `git diff --check`。
- [ ] 完成 Permission、Business、Agent、MCP 全量迁移后的相关后端测试。
  - [x] 相关 focused tests 通过；全量测试 260 通过、1 个既有 Agent error-policy 断言失败，待单独确认。
- [ ] 完成真实 Mongo、Redis、SSE 和 MCP 联调验收。
- [ ] 完成 admin-web 相关 API 测试和 TypeScript 检查（仅验证本次兼容，无需页面层重构）。
  - [x] `src/api/client.test.ts` 聚焦测试和新增文件 ESLint 通过。
  - [ ] 全量 TypeScript 检查仍有既有 API/page 类型错误，未涉及本次响应兼容改造。
- [x] 运行复杂度预算检查并处理新增代码问题。
  - [x] 设置 `PYTHONDONTWRITEBYTECODE=1` 后通过；仅保留 archive/output 和双锁文件基线警告。
- [x] 更新认证设计、API reference、安全规则和变更记录；API reference 的统一错误章节与兼容矩阵已同步。
- [x] 搜索并清理生产 API 中直接解析 `Authorization` Header 的重复逻辑；保留 Agent viewer/兼容调用所需的显式身份边界。
- [ ] 确认没有提交 `.env`、密钥、token、生成物或无关工作区变更。

## 阶段完成门槛

- [ ] Phase 0 完成：权限名、角色矩阵、dev/admin 和 viewer/acting-as 边界已评审并冻结。
- [x] Phase 1 完成：共享策略、Principal 适配器、权限依赖和错误契约均有 focused tests。
- [x] Phase 2 完成：Business REST 新增接口不再直接判断角色字符串，高风险接口完成权限和资源范围测试。
- [x] Phase 3 完成：生产 Agent handler 使用注入 Principal，viewer/兼容身份保留显式边界，SSE 鉴权前后协议行为通过测试。
- [x] Phase 4 完成：所有 MCP 工具有最小权限声明，认证通过不等于工具授权通过。
- [x] Phase 5 完成：admin-web 现有成功响应和错误读取保持兼容；完整 envelope 迁移另行立项。
- [ ] Phase 6 完成：测试、lint、架构、复杂度、文档和联调验收均有结果记录。

## 待评审决策

- [x] 接受第一阶段只增加 `Permission` 枚举和纯策略，不增加数据库权限表。
- [ ] 普通用户可查看的 Trace 工具参数和脱敏字段白名单。
- [ ] `/api/v2/dev-users` 是否要求 admin JWT，还是仅保留 loopback/development 限制。
- [x] MCP 工具权限注册表放在 Business MCP 工具包装器共享模块 `business/tools/_headers.py`，不污染 shared 角色语义。
- [ ] 是否为生产管理员模拟新增 `admin:impersonate` 和审计事件。
- [x] 完整成功 envelope 另开版本化迁移任务，本轮保持成功响应字段路径不变。
