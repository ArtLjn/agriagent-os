# 16 — Agent 日志与诊断设计

> 状态：草稿 | 维护：BlockShip | 最近校准：2026-07-30
> 关联：[07_可观测与运维](./07_可观测与运维.md)、[15_Agent运行协议与防泄漏设计](./15_Agent运行协议与防泄漏设计.md)、[06_数据飞轮与评测](./06_数据飞轮与评测.md)

---

## 1. 设计目标

Agent 日志不是“多打印一些信息”，而是把每轮请求拆成可定位、可聚合、可回放、可脱敏的证据链。

日志体系必须回答：

- 用户这一轮输入是什么？
- Router 选了哪些候选工具，为什么？
- LLM 真实调用参数是什么？
- 工具是否执行，执行结果是什么摘要？
- final 阶段是否隔离了工具历史？
- JSON / function call 泄漏是否发生，如何处理？
- 最终回复依赖了哪些证据？

非目标：

- 不在 `app.log` 中输出完整 prompt、完整工具结果、完整 JSON 参数。
- 不把 `app.log` 当成机器可读唯一事实源。
- 不记录密钥、token、连接串、鉴权头、完整 SQL、完整异常栈。

---

## 2. 四层证据体系

| 层级 | 存储 | 读者 | 用途 | 保留粒度 |
| --- | --- | --- | --- | --- |
| 人读运行日志 | `backend/app/logs/app.log` | 开发者、运维 | 快速定位现场 | 单行结构化摘要 |
| 机器读 Trace | Mongo `traceRecords` / `traceRequests` | TraceMonitor、debugger、评测 | 节点证据、耗时、输入输出摘要 | 节点 JSON |
| 流式事件 | JSONL `agent-events` | 前端回放、SSE 调试 | 流式响应、事件顺序 | event sequence |
| 问题仓 | DataFlywheel issue | 评测、回归、人工审查 | 坏例沉淀和修复闭环 | case + diagnosis |

优先级：

1. 根因分析以 trace 为主。
2. `app.log` 用于确认真实运行参数和时间线。
3. JSONL 用于检查流式输出和前端展示。
4. DataFlywheel 用于把坏例转成回归资产。

---

## 3. app.log 设计

### 3.1 日志格式

所有 Agent 运行日志必须包含：

```text
timestamp │ request_id │ logger │ level │ event=<event_name> key=value ...
```

最小字段：

| 字段 | 含义 |
| --- | --- |
| `request_id` | 请求链路 ID，无请求上下文时为 `-`。 |
| `event` | 稳定事件名，便于 `rg event=...`。 |
| `session_id` | 会话 ID，有则记录。 |
| `farm_id` | 农场 ID，有则记录。 |
| `status` | `started/success/error/blocked/retry/fallback`。 |
| `duration_ms` | 当前动作耗时。 |

### 3.2 三层日志样式

Agent 日志样式分为三种，不混用：

1. `app.log` 保持单行结构化，方便 grep、采集和告警。
2. 审计追踪块用于人读调试报告，方便在 TraceMonitor、debugger 和坏例详情中一眼看懂。
3. Trace JSON 用于机器消费，作为前端、评测和 DataFlywheel 的事实源。

#### 3.2.1 app.log 单行样式

```text
2026-07-30 13:53:23,705 │ eda446a0 │ app.agent.audit │ INFO │ event=agent_audit phase=final_response turn_id=180 run_id=run-eda446a0-r2 boundary=FINAL_NO_TOOLS sop=FINAL_CONTEXT_VALID tool_choice=none tools=0 tool_results=1 action=generate_natural_reply status=started
```

设计要点：

- 一行一个事件。
- 第一字段始终是 `event=<event_name>`。
- `phase` 标记所处阶段：`route`、`tool`、`final_response`、`output_guard`、`summary`。
- `boundary` 标记当前安全边界。
- `sop` 标记当前阶段通过的检查链。
- 只记录摘要字段，不写完整 JSON。

#### 3.2.2 审计追踪块样式

审计追踪块参考“工单 ID / Run ID / Trace ID / 边界 / SOP / 工具 / 最终动作”的排查样式，默认不直接进入 `app.log`，而是用于调试报告、TraceMonitor 复制内容和 DataFlywheel issue 详情。

```text
[审计追踪] REQ-eda446a0-FINAL final_response
工单 ID: TURN-180
Run ID: run-eda446a0-r2
Trace ID: eda446a0
Session ID: playground-1785390777662-mglp81
边界: FINAL 只生成自然语言，不允许调用工具
SOP: final_context_valid -> tool_choice_none -> output_guard_check
工具: 禁止调用；已读取工具结果 calculate_arithmetic(success)
工具结果: 30 / 1.5 = 20
最终动作: 基于工具结果生成用户回复，禁止 JSON/tool_calls/function_call
结果: success
耗时: 1683ms
------------------------------------------------------------
```

审计块固定字段：

| 字段 | 含义 |
| --- | --- |
| `工单 ID` | 用户可见对话轮次，优先使用 `turn_id`。 |
| `Run ID` | 单次运行 ID，建议由 `request_id + round_index` 组成。 |
| `Trace ID` | 排查入口，等同 `request_id`。 |
| `边界` | 当前阶段允许和禁止的行为。 |
| `SOP` | 阶段检查链，如 `tool_choice_none`。 |
| `工具` | 当前阶段绑定工具、执行工具或明确禁止工具。 |
| `工具结果` | 脱敏后的关键事实摘要。 |
| `最终动作` | 系统最终做了什么，不写内部猜测。 |
| `结果` | `success/retry/blocked/fallback/error`。 |

推荐固定五类审计块：

```text
REQ-<request_id>-ROUTE   skill_router
REQ-<request_id>-TOOL    tool_call
REQ-<request_id>-FINAL   final_response
REQ-<request_id>-GUARD   output_guard
REQ-<request_id>-SUMMARY agent_turn_summary
```

#### 3.2.3 Trace JSON 样式

```json
{
  "event": "agent_audit",
  "request_id": "eda446a0",
  "turn_id": 180,
  "run_id": "run-eda446a0-r2",
  "phase": "final_response",
  "boundary": "FINAL_NO_TOOLS",
  "sop": [
    "final_context_valid",
    "tool_choice_none",
    "output_guard_check"
  ],
  "tool_policy": {
    "tools_bound": 0,
    "tool_choice": "none",
    "raw_tool_call_history_dropped": true
  },
  "tool_results": [
    {
      "tool": "calculate_arithmetic",
      "status": "success",
      "summary": "30 / 1.5 = 20"
    }
  ],
  "final_action": "generate_natural_reply",
  "status": "success"
}
```

Trace JSON 的字段必须能稳定映射到审计追踪块，但允许比审计块更结构化。审计块是展示格式，Trace JSON 是事实源。

### 3.3 必备事件

| 事件 | 触发点 | 必备字段 |
| --- | --- | --- |
| `agent_turn_started` | 请求进入 Chat UseCase | `session_id`、`farm_id`、`entrypoint` |
| `task_state_relevance_checked` | TaskState 相关性门 | `should_inject`、`score`、`decision` |
| `skill_router_decided` | Router 完成 | `selected_tools`、`fallback`、`tool_choice` |
| `llm_call_started` | 每次 LLM 调用前 | `role`、`model`、`selected_tools`、`tool_choice`、`message_count` |
| `llm_call_finished` | 每次 LLM 调用后 | `finish_reason`、`tool_calls`、`tokens`、`duration_ms` |
| `tool_call_started` | 工具执行前 | `tool`、`operation`、`arg_keys` |
| `tool_call_finished` | 工具执行后 | `tool`、`status`、`duration_ms`、`result_preview` |
| `final_context_built` | final 上下文构建后 | `tool_result_count`、`dropped_tool_call_history`、`message_count` |
| `final_output_guard_checked` | 输出检查后 | `passed`、`leak_type`、`action` |
| `agent_turn_summary` | 请求结束 | `status`、`duration_ms`、`tool_results`、`reply_len` |

### 3.4 禁止记录

- 完整 `api_key`、token、cookie、Authorization。
- 完整 DB URL、Mongo URI、Redis URI。
- 完整 prompt。
- 完整工具参数 JSON。
- 完整 ToolMessage。
- 用户上传文件全文。
- provider 返回的完整原始响应。

可记录替代物：

- `arg_keys` 替代完整参数。
- `reply_preview` 替代完整回复。
- `result_preview` 替代完整工具结果。
- `api_key_slot=1/3` 替代真实 key。
- `base_url_host` 替代完整 URL；如必须定位 provider，可记录脱敏后的 host。

---

## 4. Trace 节点设计

Trace 是机器可读事实源，节点 envelope 沿用 [07_可观测与运维](./07_可观测与运维.md) 的 JSON 设计。

新增 Agent 运行协议相关节点：

| 节点 | 说明 |
| --- | --- |
| `final_context.build` | 记录 final 输入从 ReAct 历史投影为干净上下文的结果。 |
| `output_guard.final_json_leak_check` | 记录 JSON / function call 泄漏检测结果。 |
| `reflection_check.post_tool_result` | 记录工具结果是否被最终回复丢弃。 |
| `response.final_reply_data_source` | 记录最终回复依赖 context 还是具体 tool。 |

`final_context.build` 示例：

```json
{
  "node_type": "final_context",
  "node_name": "build",
  "input_data": {
    "source_message_count": 3,
    "has_tool_results": true,
    "tool_result_count": 1
  },
  "output_data": {
    "final_message_count": 1,
    "dropped_tool_call_history": true,
    "tool_results": [
      {
        "tool_name": "calculate_arithmetic",
        "status": "success",
        "summary": "计算结果：20"
      }
    ]
  },
  "status": "success"
}
```

`output_guard.final_json_leak_check` 示例：

```json
{
  "node_type": "output_guard",
  "node_name": "final_json_leak_check",
  "input_data": {
    "reply_len": 128,
    "has_tool_results": true
  },
  "output_data": {
    "passed": false,
    "leak_type": "content_tool_call_json",
    "action": "retry_generation",
    "retry_count": 1
  },
  "status": "blocked"
}
```

---

## 5. Function Call 日志设计

Function Call 相关日志分三类：

| 类别 | 记录位置 | 示例字段 |
| --- | --- | --- |
| 工具绑定决策 | Router trace + `app.log` | `selected_tools`、`tool_choice`、`force_binding` |
| LLM 原生输出摘要 | LLM trace + `app.log` | `finish_reason`、`tool_calls_count`、`tool_names` |
| 泄漏检测结果 | Output Guard trace + `app.log` | `leak_type`、`retry_count`、`fallback_reason` |

严禁把原始 function call JSON 直接写入 `app.log`。Trace 中也只能记录脱敏摘要：

```json
{
  "tool_calls": [
    {
      "id": "call_xxx",
      "name": "calculate_arithmetic",
      "args_summary": {
        "expression": "30 / 1.5",
        "precision": "0"
      }
    }
  ]
}
```

写操作参数必须进一步脱敏，只保留字段名和风险摘要：

```json
{
  "tool_calls": [
    {
      "name": "manage_cost",
      "arg_keys": ["amount", "category", "occurred_at"],
      "risk": "write_confirm"
    }
  ]
}
```

---

## 6. JSON 泄漏诊断规则

出现以下任一情况，生成 `json_leak_detected` 诊断：

- no-tools final 回复含疑似工具 JSON。
- final 回复含原生 `response.tool_calls`。
- final 回复整体为 JSON 对象或数组。
- final 回复夹带普通 JSON 对象或数组片段。
- final 回复含 `function_call`、`tool_calls`、`arguments`。
- final 回复输出“不需要再调用工具”“无需再调用工具”等工具协议话术。
- final 回复被 reflection 替换为与工具结果矛盾的兜底文案。

诊断字段：

| 字段 | 含义 |
| --- | --- |
| `phase` | `tool_phase` 或 `final_response_phase`。 |
| `leak_type` | `native_tool_calls`、`content_tool_call_json`、`raw_json_object`、`raw_json_output`、`protocol_keyword`。 |
| `had_tool_results` | 是否已有工具结果。 |
| `action` | `retry_generation`、`extract_text`、`fail_closed`。 |
| `regression_seed` | 是否进入回归集。 |

---

## 7. DataFlywheel 入仓规则

以下情况必须入仓：

1. `json_leak_detected`：final 阶段 JSON / function call 泄漏触发 Output Guard，尤其是二次重试失败。
2. `tool_result_discarded_reply`：有工具结果却回复“需要先调用工具”，或 reflection 发现工具结果被丢弃。
3. `trace_log_inconsistent`：trace 显示 `tool_choice=none`，但 app.log 显示真实 invocation 是 `auto`。

入仓内容：

- `request_id`
- `session_id`
- 用户输入和助手最终回复。
- Router 选择摘要。
- 工具调用摘要。
- final context 摘要。
- output guard 诊断。
- 修复建议标签。

---

## 8. 排查手册

### 8.1 用户看到工具 JSON

1. 查 `request_id` 的 `llm_call_started`，确认 final 阶段真实 `tool_choice`。
2. 查 `final_context.build`，确认是否丢弃原始 tool call 历史。
3. 查 `output_guard.final_json_leak_check`，确认是否检测和重试。
4. 查最终 `agent_response.final_reply`，确认是否被 fallback 覆盖。

### 8.2 用户看到“需要先调用工具”

1. 查本轮是否已有 `skill_call.* status=success`。
2. 如果已有工具结果，检查 `reflection_check.post_tool_result`。
3. 如果 final 回复曾泄漏 JSON，检查 fallback 文案是否按有工具结果场景处理。
4. 把 case 标记为 `tool_result_discarded_reply` 或 `final_json_leak_after_tool_result`。

### 8.3 Trace 与 app.log 不一致

1. 以 `app.log` 的 `llm_call_started` 为真实 invocation 参数。
2. trace 只能作为节点摘要；如果 trace 使用推导值，必须修 trace 记录。
3. 增加 `trace_log_inconsistent` DataFlywheel issue。

---

## 9. 指标

| 指标 | 计算方式 | 告警阈值 |
| --- | --- | --- |
| `final_json_leak_count` | `output_guard.passed=false` | 任意出现即入仓 |
| `final_tool_choice_mismatch_count` | trace 与 app.log 不一致 | 任意出现即修 |
| `tool_result_discarded_count` | reflection issue | 每日超过 3 次告警 |
| `final_context_contract_violation_count` | final context 校验失败 | 任意出现即阻断 |
| `unsafe_log_field_count` | 日志脱敏扫描 | 任意出现即阻断 PR |

---

## 10. 落地清单

1. `app.log` 统一 Agent event 字段命名。
2. `llm_call_started` 记录真实 `tool_choice`，不做推导。
3. 新增 `final_context.build` trace。
4. 新增 `output_guard.final_json_leak_check` trace。
5. DataFlywheel 支持 `json_leak_detected` 和 `trace_log_inconsistent` issue 类型。
6. TraceMonitor 展示 final 阶段工具隔离状态。
7. TraceMonitor 和 `trace-chain-debugger` 支持导出审计追踪块。
8. 日志脱敏检查加入 CI 或 harness 检查。
