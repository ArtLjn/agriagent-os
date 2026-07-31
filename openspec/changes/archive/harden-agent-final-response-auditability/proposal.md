## Why

近期 Agent 工具调用链路暴露出一个高风险问题：最终回复阶段虽然语义上“不再绑定工具”，但真实 LLM 调用和消息上下文仍可能携带工具协议痕迹，导致 function call JSON 泄漏或错误兜底为“需要先调用工具”。随着 Agent Runtime、Trace、DataFlywheel 持续迭代，需要把 Final Agent 隔离、审计日志样式和诊断闭环固化为可实施的工程任务。

## What Changes

- 新增 Final Agent 阶段契约：工具执行后必须通过 FinalContextBuilder 构造干净上下文，最终 LLM 调用必须使用 `tools=[]` 与 `tool_choice=none`。
- 新增 Output Guard：检测原生 tool calls、疑似 function call JSON、协议关键字和整段 JSON 输出；支持一次重试、自然语言抽取或 fail-closed。
- 调整有工具结果时的兜底策略：不得再返回“需要先调用工具”，必须区分“已有工具结果但回复格式异常”和“无可靠工具结果”。
- 建立三层日志样式：`app.log` 单行结构化、审计追踪块、Trace JSON。
- 扩展 trace 节点：记录 final context 构建、真实 tool_choice、输出泄漏检测和最终回复数据源。
- 扩展 TraceMonitor/debugger/DataFlywheel：支持导出审计追踪块，并把 JSON 泄漏、工具结果丢弃、trace 与 app.log 不一致沉淀为坏例。

## Capabilities

### New Capabilities

- `agent-final-response-auditability`: 定义 FinalContextBuilder、Final Agent 无工具调用、Output Guard、防 function call JSON 泄漏和有工具结果时的安全兜底行为。

### Modified Capabilities

- `llm-tool-calling`: 明确工具调用阶段和最终回复阶段的边界，final 阶段不得绑定工具或透传原始 tool call 历史。
- `agent-structured-logging`: 增加 Agent 审计日志字段、单行 app.log 样式和审计追踪块导出格式。
- `agent-trace`: 增加 final context、output guard、真实 invocation 参数和数据源节点要求。
- `trace-monitor-ui`: 增加审计追踪块展示与复制能力，支持定位 final 防泄漏诊断。

## Impact

- 后端 Runtime：`backend/app/agent/runtime/*` 的 LLM 调用、消息压缩、final 回复生成、输出过滤和 reflection 兜底链路。
- 后端 Trace/日志：`backend/app/infra/trace*`、`backend/app/agent/runtime/node_helpers.py`、`backend/app/agent/runtime/llm_invocation.py`、`backend/app/agent/runtime/chat_fallbacks.py`。
- Admin Web：TraceMonitor timeline / drawer / copy export。
- DataFlywheel：新增 JSON 泄漏和 trace-log 不一致 issue 类型。
- 测试：新增 runtime 单测、trace 断言、TraceMonitor 展示测试和一条以 `eda446a0` 为代表的回归种子。
