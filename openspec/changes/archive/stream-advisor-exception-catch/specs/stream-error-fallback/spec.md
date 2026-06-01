## ADDED Requirements

### Requirement: 流式调用通用异常兜底

`stream_advisor` 在 `graph.astream()` 抛出任何 `Exception` 子类异常时，SHALL 捕获该异常并 yield 友好的中文错误提示文本，而非让异常穿透导致 SSE 流中断。

#### Scenario: LLM 连接失败

- **WHEN** `graph.astream()` 内部抛出 `openai.APIConnectionError`
- **THEN** `stream_advisor` yield "抱歉，AI 服务暂时不可用，请稍后重试。"
- **AND** SSE 流正常关闭（客户端收到 `[DONE]`）
- **AND** error 日志记录异常类型和消息

#### Scenario: LLM 限流

- **WHEN** `graph.astream()` 内部抛出 `openai.RateLimitError`
- **THEN** `stream_advisor` yield "抱歉，AI 服务暂时不可用，请稍后重试。"
- **AND** SSE 流正常关闭

#### Scenario: 未知运行时异常

- **WHEN** `graph.astream()` 内部抛出任意 `Exception` 子类（非 `GraphRecursionError`）
- **THEN** `stream_advisor` yield "抱歉，AI 服务暂时不可用，请稍后重试。"
- **AND** error 日志记录异常类型和消息

### Requirement: 异常时 trace 清理仍执行

`stream_advisor` 发生任何异常时，`finally` 块中的 `clear_trace()` SHALL 正常执行，不遗漏 trace 清理。

#### Scenario: 异常后 trace 清理

- **WHEN** `graph.astream()` 抛出异常被 `except Exception` 捕获
- **THEN** `clear_trace()` 在 `finally` 中正常调用
- **AND** 无 trace 残留

### Requirement: 正常流程不受影响

当 `graph.astream()` 正常完成（无异常抛出）时，`stream_advisor` 的行为 SHALL 与修改前完全一致。

#### Scenario: 正常流式对话

- **WHEN** `graph.astream()` 正常 yield 所有事件后结束
- **THEN** `stream_advisor` 正常 yield 所有 LLM 回复 chunks
- **AND** 不触发 `except Exception` 分支
- **AND** `finally` 中 `clear_trace()` 正常执行

#### Scenario: 步数超限仍走原有逻辑

- **WHEN** `graph.astream()` 抛出 `GraphRecursionError`
- **THEN** 走原有的 `except GraphRecursionError` 分支
- **AND** yield "Agent 处理步数超出限制，请简化您的问题后重试。"
- **AND** 不触发新增的 `except Exception` 分支
