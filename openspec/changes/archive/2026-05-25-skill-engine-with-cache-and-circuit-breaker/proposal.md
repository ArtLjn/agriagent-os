## Why

当前 AI Agent 的 4 个工具函数（天气、周期、农事记录、成本）硬编码在 `agents/tools.py` 中，耦合度高、无法动态扩展。LLM 每次请求都重新调用所有工具，天气等非实时数据重复拉取浪费 token 和时间。LLM 调用缺乏超时/熔断保护，一旦 API 异常会导致整个请求链路阻塞失败。

已有 [skillify](https://github.com/ArtLjn/skillify) SDK 提供 Skill 基类、自动发现、Pattern 匹配、校验框架，可直接复用。

## What Changes

- 引入 skillify SDK，将 `agents/tools.py` 中的工具迁移为继承 `skillify.Skill` 的独立模块
- 实现 skillify → LangChain Tool 桥接层，让 LLM 通过 function call 调用 skillify Skill
- 自定义并行执行节点：LLM 返回多个 tool_calls 时用 asyncio 并发执行
- 为 LLM 调用添加熔断器（Circuit Breaker）和指数退避重试
- 对非实时 Skill 增加 TTL 缓存装饰器，避免重复请求

## Capabilities

### New Capabilities
- `skillify-integration`: skillify Skill 子类实现、SkillManager 初始化、skillify → LangChain StructuredTool 桥接
- `parallel-skill-executor`: 自定义 LangGraph 节点，多 tool_calls 并发执行
- `llm-circuit-breaker`: LLM 调用熔断器（CLOSED→OPEN→HALF_OPEN 三态）、指数退避重试
- `skill-cache`: TTL 缓存装饰器，按 Skill 粒度配置缓存时间

### Modified Capabilities
<!-- 无现有 spec 需要修改 -->

## Impact

- **代码变更**: 新增 `backend/app/skills/` 目录（5-6 个 Skill 文件）+ `core/circuit_breaker.py` + `core/skill_cache.py`，修改 `agents/graph.py`、`agents/advisor.py`、`core/llm.py`
- **依赖变更**: 新增 `skillify`（本地包安装），无额外外部依赖
- **API 影响**: 无 API 接口变更，纯内部架构优化
- **性能影响**: 缓存命中时天气 Skill 响应从 ~3s 降至 ~1ms；并行执行减少多工具调用总耗时
