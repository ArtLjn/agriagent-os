## Context

当前 Agent 系统的可观测性严重不足。日志只能看到请求进入和回复返回，中间的关键环节不可见：
- LLM 如何决定调用哪个 Skill（工具选择决策）
- Skill 执行的详细参数和耗时
- Prompt 模板的选择、渲染变量和最终内容
- 写操作 Skill 的确认/取消/修改流程
- LLM 调用的耗时和 token 消耗

`AgentTrace` 模型（`app/models/agent_trace.py`）已定义了 `agent_traces` 表结构，但从未被写入——是死代码。

## Goals / Non-Goals

**Goals:**
- 在 `_llm_node` 中记录 LLM 响应的工具选择决策和参数
- 在 Skill 执行流程中增加结构化日志（开始、耗时、结果摘要）
- 在 `pending_actions.py` 中记录完整生命周期
- 在 `prompt_renderer.py` 中记录模板选择和渲染变量（DEBUG 级别）
- 激活 `AgentTrace` 模型，在关键节点写入追踪记录
- 统一日志格式：`key=value` 键值对风格，方便 grep

**Non-Goals:**
- 不引入新的日志框架或 APM 工具（如 OpenTelemetry）
- 不修改日志文件轮转策略（已有 `RotatingFileHandler`）
- 不记录完整的 LLM 请求/响应体（数据量太大，只记摘要）
- 不修改前端展示层

## Decisions

### D1: 日志增强 vs 独立追踪表

**选择：两者并行。**

- **日志增强**（`logger.info`）：零侵入，开发/排查时直接 grep，满足 80% 场景
- **`AgentTrace` 表写入**：持久化、可查询、支持历史分析，满足 20% 场景（统计、审计）

理由：单独用日志难以做统计查询，单独用追踪表开发体验差。两者互补。

### D2: AgentTrace 写入方式

**选择：同步写入，在 graph 节点返回前完成。**

理由：
- AgentTrace 写入很轻（单条 INSERT），耗时可忽略
- 异步写入需要管理后台任务生命周期，增加复杂度
- 当前系统是单用户农场管理工具，并发量极低

替代方案：后台 asyncio Task 写入 — 增加了错误处理复杂度，收益不大。

### D3: 日志格式

**选择：结构化键值对格式，延续现有风格。**

```
2026-05-26 │ abc123 │ app.agents.graph │ INFO │ LLM 响应 | tool_calls=[get_weather] | model=qwen3.6-flash
```

不引入 JSON 日志格式 — 项目规模小，grep 友好更重要。

### D4: 日志级别策略

| 级别 | 使用场景 |
|------|---------|
| DEBUG | 模板渲染变量、完整 system prompt 内容、消息压缩详情 |
| INFO | Skill 发现列表、LLM 工具选择、Skill 执行开始/完成、pending action 生命周期 |
| WARNING | 模板回退、上下文获取失败、pending action 超时 |
| ERROR | Skill 执行失败、LLM 调用失败 |

生产环境默认 INFO，排查问题时临时调为 DEBUG。

### D5: AgentTrace 表结构确认

现有模型已满足需求，只需新增 `session_id` 写入逻辑：
- `session_id` = `request_id`（从 `ContextVar` 获取），用于关联同一请求的所有追踪记录
- `node_type`：`llm_call` / `tool_call`
- `node_name`：Skill 名称 或 `llm`
- `input_summary` / `output_summary`：截断到 500 字符
- `duration_ms`：毫秒级计时
- `tokens_used`：从 LLM 响应 metadata 提取（如可用）

## Risks / Trade-offs

- [日志量增加] → 通过 DEBUG/INFO 分级控制，生产环境默认 INFO，关键节点日志量增加约 3-5 条/请求，可接受
- [AgentTrace 表增长] → 当前单用户场景增长极慢，后续可加定时清理（保留 30 天）
- [性能影响] → AgentTrace 单条 INSERT < 1ms，同步写入对响应时间影响可忽略
- [LLM 响应 metadata 不一定包含 token 信息] → `tokens_used` 设为 nullable，缺失时记 None
