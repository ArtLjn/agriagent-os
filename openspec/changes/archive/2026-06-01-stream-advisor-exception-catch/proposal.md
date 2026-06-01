## Why

`stream_advisor` 的 `async for event in graph.astream(...)` 只 catch 了 `GraphRecursionError`，LLM 层的 `APIConnectionError`、`RateLimitError` 等异常直接穿透到 API 层，导致 SSE 流中断，用户看到连接错误而非友好提示。日志中已有 8 次相关未捕获异常记录。

Spike 验证已确认 `except Exception` 兜底在 async generator 中可以正常 yield + finally 执行。

## What Changes

- 在 `advisor.py` 的 `stream_advisor` 函数中，`except GraphRecursionError` 之后增加 `except Exception` 通用兜底
- 兜底 yield 友好错误提示，记录 error 日志（含异常类型和消息）
- `finally` 中的 `clear_trace()` 不受影响（spike 验证通过）

## Capabilities

### New Capabilities

- `stream-error-fallback`: 流式调用链的通用异常兜底，确保 LLM/网络异常不会导致 SSE 流直接断开，用户收到可读的错误提示

### Modified Capabilities

（无已有 spec 需要修改）

## Impact

- **代码**: `backend/app/agent/advisor.py` — `stream_advisor` 函数增加 3 行 except 块
- **API**: `/agent/chat/stream` SSE 端点行为变化 — 异常时返回友好文本而非连接中断
- **日志**: error 级别日志增加 `Agent 流式异常` 记录，包含异常类型
- **无 breaking change**: 正常流程完全不受影响（spike Test 3 验证）
