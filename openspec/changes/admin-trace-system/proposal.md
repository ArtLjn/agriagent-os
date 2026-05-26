## Why

当前系统没有任何 LLM 执行链路可视化能力。开发者调试时面对的问题：
- "LLM 为什么没调 skill？" — 看不到 system prompt 渲染结果、tool_calls 返回值
- "skill 执行耗时多少？" — 没有计时，只有 `logger.info` 打印
- "这次对话花了多少 token？" — 完全没有统计
- "用户反馈回复不对，怎么回溯？" — 没有完整的请求/响应记录

product-agent 项目有成熟的 trace 系统（`contextvars` 链路追踪 + Gantt 图可视化），可借鉴其核心模式，用 SQLite 替代 MongoDB 存储，适配到当前 LangGraph 架构。

## What Changes

- 新增 trace 上下文管理：基于 `contextvars` 的跨异步调用追踪（借鉴 product-agent `trace_context.py`）
- 新增 trace 收集器：在 `graph.py` 的 `_llm_node` 和 `_parallel_tool_node` 中埋点，记录每次 LLM 调用和 Skill 调用的 input/output/耗时/token
- 新增 `trace_records` 数据表：SQLite 持久化 trace 数据（按 session 分组，按 round 分轮次）
- 新增 Token 用量统计：记录每次 LLM 调用的 prompt_tokens / completion_tokens，按用户/模型/调用类型汇总
- 新增 Admin API：查询 trace 数据、token 用量统计、清空历史
- 新增 Token 配额检查：调用 LLM 前检查用户日配额，超配额按策略处理（拒绝/降级/警告）

## Capabilities

### New Capabilities
- `trace-collection`: Trace 埋点收集——`contextvars` 链路追踪 + LLM/Skill/HTTP 节点记录 + SQLite 持久化
- `trace-query-api`: Trace 查询 API——按 session/record 查询执行链路，返回 Gantt 图所需数据
- `token-metering`: Token 计量——每次 LLM 调用记录 token 消耗，按用户/模型/日期汇总，配额检查
- `admin-config-api`: Admin 配置 API——运行时配置查看、API key 状态检查、缓存管理、Skill 列表

### Modified Capabilities
- `prompt-template-management`: 新增 Admin API 查看渲染后 prompt、热加载模板
