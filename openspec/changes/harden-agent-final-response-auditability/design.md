## Context

当前 Agent Runtime 使用 ReAct loop：首轮 LLM 可以绑定候选工具并产生 `tool_calls`，工具执行后再进入最终回复生成。近期 trace `eda446a0` 暴露出两个问题：一是 final 阶段日志显示“无工具”，但真实 LLM invocation 仍可能使用默认 `tool_choice=auto`；二是 final 阶段仍消费原始 `HumanMessage -> AIMessage(tool_calls) -> ToolMessage` 历史，兼容模型容易复刻工具调用 JSON，导致 no-tools JSON 泄漏和错误兜底。

项目已存在 `llm-tool-calling`、`agent-structured-logging`、`agent-trace` 和 `trace-monitor-ui` 能力。本 change 不替换这些能力，而是在它们之上增加 Final Agent 防泄漏和审计可观测闭环。

主要约束：

- 不新增第二套 Agent Runtime。
- 不改变外部聊天 API。
- 不把完整 prompt、完整工具参数、密钥、连接串或完整 ToolMessage 写入日志。
- 代码实现必须遵守现有边界：Runtime 负责消息和 LLM 调用，Trace 负责节点证据，Admin Web 只消费接口数据。

## Goals / Non-Goals

**Goals:**

- 将 Tool Agent 与 Final Agent 分阶段隔离。
- final 阶段真实使用 `tools=[]` 与 `tool_choice=none`，并在日志和 trace 中如实记录。
- 用 FinalContextBuilder 将原始 ReAct 消息历史投影为 `FinalResponseRequest`。
- 用 Output Guard 检测并处理原生 tool calls、function call JSON、协议关键字和整段 JSON 输出。
- 设计三层日志样式：单行 `app.log`、审计追踪块、Trace JSON。
- 让 TraceMonitor、trace-chain-debugger 和 DataFlywheel 能消费同一套审计证据。

**Non-Goals:**

- 不重写 Skill Router。
- 不改变 Tool Executor 权限模型。
- 不扩大写操作自动执行范围。
- 不把所有 trace 变成完整事件溯源系统。
- 不在本 change 中引入新的外部日志平台或 APM 依赖。

## Decisions

### Decision 1: FinalContextBuilder 作为 Final Agent 的唯一输入构造器

FinalContextBuilder 从 `AgentState` 中读取最后一条用户消息、已执行工具结果和可引用上下文，输出 `FinalResponseRequest`。它不得返回原始 `AIMessage(tool_calls)` 或原始 `ToolMessage`。

理由：

- 直接裁剪 `messages` 容易遗漏历史链路中的 tool call 协议。
- 独立 builder 可以被单测直接验证，也方便 trace 记录 `dropped_tool_call_history=true`。
- 后续不同 final prompt 或 provider 适配可共享同一上下文投影。

替代方案：

- 只在 prompt 中强调“不要输出 JSON”：实现快，但不能阻断消息污染。
- 在 `sliding_window_compact` 中删除 tool call：会影响非 final 阶段语义，边界不清。

### Decision 2: final LLM invocation 显式传递 `tool_choice=none`

Runtime 在 final 阶段必须把 `tool_choice` 从语义状态变成真实调用参数。日志和 trace 记录的 `tool_choice` 必须来自 invocation 参数，不得根据 `selected_tools=[]` 推导。

理由：

- `selected_tools=0` 不等于 provider 侧禁止工具协议。
- `app.log` 与 trace 不一致会误导排查。

替代方案：

- 只依赖不绑定工具的 raw LLM：对兼容模型不够稳，且日志无法证明 final contract。

### Decision 3: Output Guard 是最后防线，不替代上下文隔离

Output Guard 检测原生 `response.tool_calls`、疑似 tool JSON、`function_call` / `tool_calls` / `arguments` 等协议关键字，以及整段 JSON 输出。首次泄漏使用相同 `FinalResponseRequest` 重试一次；二次失败时尝试安全抽取自然语言，否则 fail-closed。

理由：

- 模型可能不遵守 prompt，必须有输出层保护。
- 仅靠 fail-closed 会损害可用性；有些回复可以安全抽取自然语言。

替代方案：

- 泄漏后直接返回固定兜底：简单但会丢失工具结果，且曾导致“需要先调用工具”的错误文案。

### Decision 4: 审计日志分三层

`app.log` 保持单行结构化；审计追踪块只用于人读报告和复制导出；Trace JSON 是机器事实源。

理由：

- 多行审计块不适合作为生产日志唯一格式。
- 单行日志方便 grep、采集和告警。
- 审计块更适合 TraceMonitor、debugger、DataFlywheel issue 详情。

替代方案：

- 全部使用多行审计块：排查友好，但对日志采集和聚合不友好。
- 全部使用 JSON：机器友好，但人读调试成本高。

### Decision 5: DataFlywheel 接收防泄漏坏例

以下情况进入 DataFlywheel issue：二次 JSON 泄漏、已有工具结果却回复“需要先调用工具”、trace 与 app.log 的真实 `tool_choice` 不一致、工具结果被 final 回复丢弃。

理由：

- 这类问题高度适合作为回归集和评测样本。
- 单次修复不能保证后续 provider/prompt 迭代不复发。

## Risks / Trade-offs

- [Risk] FinalContextBuilder 摘要过度压缩导致最终回复缺少关键信息 → Mitigation: `ToolResultSummary.facts` 保留结构化事实，trace 记录摘要和字段数。
- [Risk] Output Guard 误判普通 JSON 答案为泄漏 → Mitigation: final prompt 默认禁止 JSON；若未来有合法 JSON 输出场景，必须显式跳过并新增测试。
- [Risk] fail-closed 文案影响用户体验 → Mitigation: 先重试一次，再尝试安全抽取自然语言；有工具结果和无工具结果使用不同兜底。
- [Risk] 审计字段过多导致日志噪音 → Mitigation: `app.log` 只保留 key-value 摘要，审计追踪块仅用于导出，不默认写入生产日志。
- [Risk] TraceMonitor 展示依赖新增 trace 字段，旧 trace 缺字段 → Mitigation: 前端对缺失字段显示“未记录”，不阻断 timeline。

## Migration Plan

1. 增加 FinalContextBuilder 和 Output Guard 单元测试，先覆盖 `eda446a0` 类回归种子。
2. 修改 Runtime final 阶段 invocation 参数和消息输入，保持外部 API 不变。
3. 增加 trace 节点和 app.log 字段，确保日志不泄露敏感参数。
4. 增加 TraceMonitor 审计追踪块展示与复制。
5. 增加 DataFlywheel issue 规则和回归样本。
6. 若上线后出现异常，可回滚 FinalContextBuilder 接入，但保留 Output Guard 阻断泄漏。

## Open Questions

- 是否允许某些未来场景输出合法 JSON，需要单独 capability 扩展；本 change 默认 final 聊天回复不允许 JSON。
- 审计追踪块是否由后端生成还是前端根据 Trace JSON 渲染；推荐先由前端/debugger 渲染，后端只提供结构化事实。
