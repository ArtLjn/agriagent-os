# v2 Trace 调试与召回设计

本文是 `trace-chain-debugger` 的 v2 调试契约。当前 Trace `nodes/events/timeline` 查询入口已经提供，但 `traceEvents` 集合或真实环境不可用时，报告仍必须标记 `not_available`/`unavailable`，不能把空结果当成已验证证据。

## 1. 调试边界

- 只读查询 Mongo、v2 Agent Trace API、会话消息和本地 JSONL；
- 不修改业务数据、不重放 Tool、不写入 Trace；
- v2 使用字符串 `turn_id`，不能当作旧版 MySQL `agent_turns.id`；
- v2 的会话主键是 `conversation_id`，不能自动把 `session_id` 翻译成 v2 查询参数；
- 输出必须区分“没有数据”和“数据源不可用”。

## 2. 定位优先级

```text
trace_id
  -> turn_id
  -> 精确 request_id
  -> 短 request_id 前缀
  -> conversation_id
```

如果同时提供多个 ID，优先使用更精确的 ID，并在 `解析范围` 中写明被忽略或交叉验证的参数。

## 3. 单轮召回

目标：重建一轮从接入、排队、Runtime、SSE、Tool、业务提交到最终答复的链路。

```text
traces?turn_id=<turn_id>
  -> traces/<trace_id>/summary
  -> traces/<trace_id>/timeline
  -> conversations/<conversation_id> 过滤 turn_id
```

报告必须包含：

- Turn 状态、phase、stop_reason；
- `queued/accepted/started/meta` 是否存在；
- SSE `seq` 是否连续，是否出现重复或缺失；
- `approval_required -> approval_result` 是否闭合；
- `tool_started -> tool_finished -> observation` 是否闭合；
- `operation_committed` 是否真实发生；
- `final_answer` 和 assistant 消息是否存在；
- 第一个错误节点及其上游输入。

## 4. 整段会话召回

目标：按时间还原一个 `conversation_id` 的多轮上下文和执行结果。

```text
conversations/<conversation_id> 分页
  + traces?conversation_id=<conversation_id> 分页
  + 每个 trace_id 的 summary/timeline
  -> 按 created_at 合并
  -> 按 turn_id 分组
```

每一轮必须保留以下关联：

```text
conversation_id -> turn_id -> trace_id -> seq/event_id -> span_id
```

报告需要识别：

- 用户消息是否有对应 assistant 消息；
- 上一轮工具结果是否进入下一轮上下文；
- 会话中是否出现重复 Turn 或幂等重放；
- 某一轮是否写入业务但没有最终答复；
- 某一轮是否只有自然语言成功声明而没有业务提交证据。

## 5. v2 接口命名

正式名称：

```text
GET /api/v2/traces
GET /api/v2/traces/{trace_id}
GET /api/v2/traces/{trace_id}/summary
GET /api/v2/traces/{trace_id}/nodes
GET /api/v2/traces/{trace_id}/events
GET /api/v2/traces/{trace_id}/timeline
GET /api/v2/conversations/{conversation_id}
GET /api/v2/turns/{turn_id}
GET /api/v2/turns/{turn_id}/events
```

兼容名称：

```text
GET /api/v2/traces/{request_id}
GET /api/v2/traces/{request_id}/summary
```

兼容名称中的 `request_id` 只表示旧接口路径参数，内部报告仍统一输出 `trace_id`。

## 6. 目标 CLI 设计

当前已支持的命令仍然有效：

```bash
python .codex/skills/trace-chain-debugger/scripts/analyze_trace_chain.py \
  --project . --v2 --turn-id <turn_id>
```

目标扩展参数：

```text
--trace-id <trace_id>       精确召回一轮 Trace
--conversation-id <id>      召回整个 v2 会话
--turn-id <id>              召回一轮 v2 Turn
--request-id <id|prefix>    兼容旧 request_id 查询
--include-events            包含 SSE 事件时间线
--include-payload           包含经过脱敏和截断的 payload
--limit <n>                 会话轮数或分页大小
--json                      输出机器可读报告
```

参数约束：

- `--trace-id`、`--turn-id`、`--conversation-id` 三者可以单独使用；
- `--include-payload` 不能绕过脱敏规则；
- `--json` 的字段名必须稳定，错误也必须是结构化字段；
- 未实现的 `traceEvents` 接口应输出 `events=not_available(v2_api)`，不能静默显示为空。

脚本实现约定：`--v2-base-url` 默认指向 Agent 根地址，召回器自动补齐
`/api/v2`；如果传入的地址已经以 `/api/v2` 结尾则不重复拼接。节点召回先请求
`/traces/{trace_id}/nodes`，迁移期接口返回 404 时才请求兼容的
`/traces/{trace_id}`，并在证据缺口中标记 `formal_endpoint_not_implemented`。
`--include-events` 先请求 `timeline`，404 后再请求 `events`；两个接口均不可用时，
报告固定输出 `trace_events=not_available(v2_api)`。网络错误、鉴权错误和目标数据
不存在分别保留为 `unavailable`、`unavailable(code=v2_auth_*)` 和 `missing(v2)`。

## 7. 数据源和降级

| 证据 | v2 首选来源 | 降级来源 | 缺失含义 |
|---|---|---|---|
| Turn 汇总 | `traceRequestSummaries` / `/traces` | `traceRecords` 聚合 | 不能判断整轮耗时和最终状态 |
| 执行节点 | `/traces/{trace_id}/nodes` | Mongo `traceRecords` | 缺少 Runtime 细节 |
| SSE 事件 | `/traces/{trace_id}/events` | Redis/本地事件导出 | 缺少状态迁移和重放证据 |
| 聊天消息 | `/conversations/{conversation_id}` | Mongo `conversationMessages` | 缺少输入和最终答复证据 |
| 本地事件 | `event_file + event_seq_range` | `data/agent-events/.../events.jsonl` | 缺少旧链路审计事件 |

Mongo 超时、鉴权失败、服务未启动和集合不存在必须分别输出 `error`、`forbidden`、`unavailable`、`missing`，不能统一成空列表。

## 8. 调试判断顺序

```text
消息是否存在
  -> Turn 是否创建和进入运行
  -> SSE 是否有 started/meta
  -> Context/LLM 是否开始
  -> Tool 是否闭合
  -> 审批是否闭合
  -> 业务是否真实提交
  -> final_answer 是否生成和持久化
  -> done 是否唯一且状态正确
```

第一个错误节点优先级最高；后续错误可能只是级联结果。慢节点超过 5 秒时，分别比较排队、锁、LLM、MCP、审批和最终答复耗时，不能只看整轮 `duration_ms`。

## 9. 标准报告字段

```text
target
resolved_scope
evidence_status
conversation_overview
turn_overview
sse_timeline
trace_timeline
business_outcome
errors
evidence_gaps
suggestions
```

报告措辞必须区分：

- `confirmed`：有 Trace、事件或业务结果证据；
- `inferred`：由多个证据推断；
- `missing`：查询没有命中；
- `unavailable`：数据源无法访问；
- `not_implemented`：目标接口或采集能力尚未实现。
