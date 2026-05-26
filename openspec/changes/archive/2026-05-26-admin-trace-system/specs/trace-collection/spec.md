## ADDED Requirements

### Requirement: TraceContext 链路追踪上下文
系统 SHALL 基于 `contextvars` 提供跨异步调用的 trace 上下文。每次对话请求生成唯一 `request_id`，所有节点（LLM/Skill）共享同一上下文。

#### Scenario: 请求入口初始化 trace
- **WHEN** `invoke_advisor` 或 `stream_advisor` 被调用
- **THEN** 初始化 `TraceInfo(request_id=uuid4, session_id=session_id, farm_id=farm_id)`

#### Scenario: 请求结束清除 trace
- **WHEN** 对话请求完成（成功或异常）
- **THEN** 清除 `contextvars` 中的 trace 上下文

### Requirement: LLM 调用埋点
系统 SHALL 在每次 LLM 调用前后记录 trace：node_type=`llm_call`，包含渲染后的 prompt 摘要、LLM 响应摘要、token 用量、耗时。

#### Scenario: 记录 LLM 调用
- **WHEN** `_llm_node` 调用 `llm.invoke()`
- **THEN** trace 记录 input_data（system prompt 前 2000 字符 + messages 长度）、output_data（AIMessage 内容前 1000 字符 + tool_calls 摘要）、token_usage（从 response.response_metadata 提取）

#### Scenario: LLM 调用失败
- **WHEN** `llm.invoke()` 抛出异常
- **THEN** trace 记录 status=`error`，error_message 为异常信息，duration_ms 为已耗时间

### Requirement: Skill 调用埋点
系统 SHALL 在每个 Skill 执行前后记录 trace：node_type=`skill_call`，包含调用参数、返回结果摘要、耗时。

#### Scenario: 记录 Skill 调用
- **WHEN** `_parallel_tool_node` 执行 `tool.ainvoke(args)`
- **THEN** trace 记录 node_name=skill 名称、input_data=args、output_data=result 前 2000 字符、duration_ms

#### Scenario: Skill 调用失败
- **WHEN** `tool.ainvoke()` 抛出异常
- **THEN** trace 记录 status=`error`，error_message 为异常信息

### Requirement: Prompt 渲染埋点
系统 SHALL 在每次 system prompt 渲染时记录 trace：node_type=`prompt_render`，包含渲染后的完整 prompt 和注入的变量值。

#### Scenario: 记录 prompt 渲染
- **WHEN** `_llm_node` 调用 `render_prompt("system_base", ...)`
- **THEN** trace 记录 node_name=`system_prompt`、input_data=变量值 dict、output_data=渲染后完整 prompt

### Requirement: Round 追踪
系统 SHALL 为每次对话请求追踪 round 索引（第几轮 LLM 循环）。首轮 round_index=0，tool 执行后再次进入 _llm_node 时 round_index=1，以此类推。

#### Scenario: 首轮对话
- **WHEN** 用户发送消息，首次进入 `_llm_node`
- **THEN** 该轮所有 trace 记录 round_index=0

#### Scenario: Tool 后第二轮
- **WHEN** Skill 执行完毕，再次进入 `_llm_node`
- **THEN** 该轮 trace 记录 round_index=1

### Requirement: Trace 异步持久化
Trace 数据 SHALL 通过内存队列异步批量写入 SQLite，不阻塞请求线程。

#### Scenario: 正常写入
- **WHEN** `TraceCollector.record()` 被调用
- **THEN** 数据放入内存队列，后台 worker 每 5 秒或积累 20 条时批量 INSERT

#### Scenario: 队列满时降级
- **WHEN** 内存队列超过 1000 条
- **THEN** 丢弃最早的 trace 数据，记录 warning 日志

### Requirement: Trace TTL 自动清理
Trace 数据 SHALL 自动清理：`trace_records` 保留 7 天，`token_daily_stats` 保留 90 天。

#### Scenario: 启动时清理
- **WHEN** 后端服务启动
- **THEN** 执行一次 `DELETE FROM trace_records WHERE created_at < datetime('now', '-7 days')`

#### Scenario: 定时清理
- **WHEN** 每日 00:00
- **THEN** 清理过期的 trace_records 和 token_daily_stats
