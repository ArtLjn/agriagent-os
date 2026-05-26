## Context

当前 Farm Manager 系统（后端 FastAPI + 前端 React Admin-web + 移动端）处于开发初期。后端已实现 LangGraph Agent + Skill 引擎 + 熔断器 + 缓存，但安全防护和可观测性几乎为零。前端 Admin-web 只覆盖了 Create/Read，缺少 Edit/Delete、分页、类型定义和统一错误处理。

核心约束：
- 后端使用 DashScope（非 OpenAI），但通过 `langchain-openai.ChatOpenAI` 兼容接口接入
- LangGraph Agent 已有 `_should_continue` 条件边，但无 recursion_limit
- 当前 SQLite 单文件数据库，单进程部署
- 开发环境为主，尚未上线生产

## Goals / Non-Goals

**Goals:**

- Agent 调用不会无限循环，单次请求有明确的步数和 Token 上限
- LLM 输出（特别是 cost_service.parse_record）不直接入库，必须经过校验
- 全局异常有统一格式，不泄漏堆栈
- 所有 API 有基础限流保护
- 通过 LangSmith 能看到 Agent 每步决策、Token 消耗、延迟拆解
- Admin-web 所有数据页面支持完整 CRUD + 分页

**Non-Goals:**

- 不实现完整的 JWT 认证系统（仅预留扩展点，当前使用 API Key）
- 不实现 Human-in-the-Loop 审批流（Agent 当前所有 Skill 都是只读，风险可控）
- 不实现向量数据库/长期记忆（当前无此需求）
- 不实现 Skill 沙箱隔离（Skill 都是只读查询，无破坏性）
- 不做移动端改动

## Decisions

### D1: Agent Max Steps 限制方式

**选择**: 使用 LangGraph 的 `recursion_limit` 编译参数

**理由**: LangGraph 原生支持，在 `graph.compile(recursion_limit=N)` 中设置即可。当步数超限时 graph 自动抛出 `GraphRecursionError`，无需修改图结构。

**替代方案**:
- 在 `_should_continue` 中手动计数：需要修改 AgentState 增加计数器，侵入性大
- 中间件层限制：无法感知 LangGraph 内部步数

**限制值**: 设为 15（典型农事问答 3-5 步工具调用，留 3 倍余量）

### D2: 输入/输出审核策略

**选择**: 轻量级正则 + 关键词黑名单，不用专门的审核模型

**理由**: 当前是农业场景，攻击面有限。专门的 Llama Guard 等模型需要额外部署，增加复杂度和延迟。先用规则引擎覆盖 80% 场景，后续按需升级。

**实现**:
- 输入：检测常见注入模式（"忽略指令"、"ignore previous"、"system:"）+ 敏感词黑名单
- 输出：PII 正则过滤（手机号、身份证号、API key 格式）+ JSON Schema 校验

### D3: 可观测性方案选择

**选择**: LangSmith（SaaS）

**理由**: 项目已使用 LangChain + LangGraph，LangSmith 是原生配套。接入只需 2 个环境变量 + 1 个 pip 包，零运维。开发阶段用测试数据，无隐私合规问题。

**替代方案**:
- Langfuse（自部署）：需运维 Docker/Postgres，开发期过重
- Phoenix（本地）：功能较新，与 LangGraph 集成不如 LangSmith 成熟
- 自建：投入产出比差

**成本控制**: 免费版 5000 trace/月，开发期足够；后续切自部署 Langfuse 只需换环境变量

### D4: 全局异常处理

**选择**: FastAPI `@app.exception_handler` 注册全局处理器

**实现**:
- `Exception` → 500，返回 `{"detail": "内部服务器错误"}`，记录完整堆栈到日志
- `HTTPException` → 原样返回，保留 status code 和 detail
- `RequestValidationError` → 422，返回结构化字段错误
- `GraphRecursionError` → 429，返回"Agent 步数超限"

### D5: 限流方案

**选择**: `slowapi` 库（基于令牌桶算法）

**理由**: 轻量，与 FastAPI 集成好（`@limiter.limit("30/minute")` 装饰器），基于 IP 限流。无需 Redis，内存存储即可满足单进程部署。

**限流策略**: 全局 30 次/分钟/IP，Agent 接口 10 次/分钟/IP

### D6: farm_id 越权修复

**选择**: 统一使用 `Depends(get_current_farm)` 依赖注入

**修改范围**: `cost.py` 和 `cost_categories.py` 中 `farm_id: int = Query(...)` 改为 `farm: Farm = Depends(get_current_farm)`，使用 `farm.id`

### D7: Admin-web CRUD 补全模式

**选择**: Edit 用 Modal 弹窗（与 Create 复用表单组件），Delete 用 Popconfirm 二次确认

**分页**: 使用 Ant Design `<Table>` 的 `pagination` prop，后端统一返回 `{ items, total }` 格式

## Risks / Trade-offs

- [LangSmith 数据上传] → 开发环境只用测试数据，生产环境切换为 Langfuse 自部署
- [recursion_limit=15 可能阻断合法长链路] → 记录被阻断的请求，后续按实际使用调整
- [正则审核有误报率] → 记录每次拦截日志，定期回顾调整规则
- [slowapi 内存存储重启丢失] → 单进程部署可接受；多实例部署时切 Redis 存储
- [Edit/Delete 无权限控制] → 当前无认证系统，危险操作加前端二次确认兜底；后续接 JWT 后再细化权限
