## Context

`stream_advisor` 是 SSE 流式对话的核心函数，调用 `graph.astream()` 驱动 LangGraph Agent 图。当前异常处理链：

```
graph.astream() 抛异常
  → stream_advisor 只 catch GraphRecursionError
    → stream_chat_with_agent 冒泡
      → agent.py event_generator 只 catch LlmNotConfiguredError
        → SSE 流断开，用户看到连接错误
```

Spike 验证（`spike-async-gen-exception.py`）已确认：async generator 的 `except Exception` 内可以正常 yield，且 `finally` 始终执行。

## Goals / Non-Goals

**Goals:**

- LLM 连接异常时用户收到友好文本提示，SSE 流优雅关闭
- `clear_trace()` 在异常时仍正常执行
- 不改变正常流程的任何行为

**Non-Goals:**

- 不在 `agent.py` 的 event_generator 增加兜底（职责分离，stream_advisor 应自行处理）
- 不做异常分类（区分连接错误/限流/超时等），统一提示即可
- 不修改 `invoke_advisor`（非流式调用由 API 层统一处理）

## Decisions

### Decision 1: 兜底放在 `stream_advisor` 而非 `agent.py`

**选择**: 在 `advisor.py` 的 `stream_advisor` 内加 `except Exception`

**备选方案**: 在 `agent.py` 的 `event_generator` 加通用 catch

**理由**: 异常处理应靠近出错点。`stream_advisor` 是 async generator 的生产方，它自己最清楚什么算异常。如果放在 `agent.py`，则 `stream_advisor` 的 `clear_trace()` 可能还没执行异常就冒泡了。spike 验证 confirm 放在 stream_advisor 内 finally 正常执行。

### Decision 2: 错误消息写死中文自然语言

**选择**: `yield "抱歉，AI 服务暂时不可用，请稍后重试。"`

**备选方案**: yield 结构化 JSON `{"error": "..."}` 让前端特殊处理

**理由**: 当前 SSE 协议中，`agent.py` 的 event_generator 对每个 chunk 都包装为 `{"content": chunk}`。错误文本走同样的路径，前端无需区分是正常回复还是错误提示。保持简单。

### Decision 3: 只 catch `Exception`，不 catch `BaseException`

**选择**: `except Exception`

**理由**: `KeyboardInterrupt` / `SystemExit` 等 `BaseException` 不应被吞掉，应让进程正常退出。

## Risks / Trade-offs

- **[Risk] 错误提示会被存入 AgentRecord]** → 可接受。`agent.py` 的 event_generator 会将 yield 的文本存到数据库，"AI 服务暂时不可用"作为对话记录也合理，用户下次能看到上次出了问题。
- **[Risk] 过度 catch 掩盖未知 bug]** → 通过 error 日志含完整异常类型缓解。`logger.error("Agent 流式异常 | farm_id=%s | error=%s", farm_id, e)` 会记录异常信息，排查时可追溯。
