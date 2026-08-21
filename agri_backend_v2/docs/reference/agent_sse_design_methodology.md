# Agent Harness：SSE 流输出设计方法论

## 1. 设计目标

Agent SSE 不应该只是把内部日志实时打印给前端。

它应该是：

> **Agent Harness Execution State 的事件流（Execution Event Stream）**

SSE 的核心职责是让客户端能够理解：

-   Agent 当前处于什么阶段
-   当前正在执行什么
-   一个 Step 如何开始和结束
-   Tool 是否执行
-   Agent 是否产生最终结果
-   Turn 为什么结束
-   是否发生错误

因此：

``` text
SSE ≠ Log Stream
SSE = Execution Event Stream
```

------------------------------------------------------------------------

## 2. 推荐的整体结构

``` text
                    Agent Harness
                         │
                         ↓
                    Turn Runtime
                         │
                ┌────────┴────────┐
                ↓                 ↓
             Context           Control
                │                 │
                └────────┬────────┘
                         ↓
                     Event Bus
                         ↓
                    SSE Adapter
                         ↓
                      Client
```

核心原则：

> Agent 内部产生结构化事件，SSE 只是其中一种输出协议。

因此不要让 Agent Runtime 直接拼 SSE 字符串。

推荐：

``` text
Agent Runtime
    ↓
Domain Event
    ↓
Event Bus
    ↓
SSE Serializer
    ↓
HTTP SSE
```

------------------------------------------------------------------------

## 3. Event 与 SSE 的区别

内部事件：

``` json
{
  "type": "step.started",
  "turn_id": "turn_123",
  "step_id": "step_4"
}
```

SSE：

``` text
event: step.started
data: {"turn_id":"turn_123","step_id":"step_4"}
```

所以：

``` text
Domain Event
    ↓
Transport Event
```

不要把 SSE 格式直接设计成 Agent 内部的数据模型。

这样未来可以同时支持：

``` text
SSE
WebSocket
Webhook
Message Queue
Tracing
```

------------------------------------------------------------------------

## 4. Event 分类

推荐将事件分成五层。

``` text
Turn Events
Step Events
LLM Events
Tool Events
Control Events
```

整体：

``` text
Agent Event Stream
│
├── Turn
│   ├── turn.started
│   ├── turn.completed
│   ├── turn.terminated
│   └── turn.failed
│
├── Step
│   ├── step.started
│   └── step.completed
│
├── LLM
│   ├── message.started
│   ├── reasoning.delta
│   ├── message.delta
│   └── message.completed
│
├── Tool
│   ├── tool.started
│   ├── tool.input
│   ├── tool.completed
│   └── tool.failed
│
└── Control
    ├── turn.paused
    ├── turn.resumed
    └── turn.cancelled
```

------------------------------------------------------------------------

## 5. Turn Event

Turn 是最高层生命周期。

### turn.started

``` json
{
  "type": "turn.started",
  "turn_id": "turn_123"
}
```

### turn.completed

``` json
{
  "type": "turn.completed",
  "turn_id": "turn_123"
}
```

### turn.terminated

用于受控终止：

``` json
{
  "type": "turn.terminated",
  "turn_id": "turn_123",
  "reason": "max_steps",
  "step_count": 20
}
```

### turn.failed

用于真正异常：

``` json
{
  "type": "turn.failed",
  "turn_id": "turn_123",
  "error": {
    "code": "TOOL_EXECUTION_FAILED",
    "message": "Tool execution failed"
  }
}
```

------------------------------------------------------------------------

## 6. Step Event

Step 是 Agent Loop 的基本执行单元。

``` text
Step
 │
 ├── step.started
 │
 ├── reasoning / LLM
 │
 ├── tool
 │
 └── step.completed
```

例如：

``` json
{
  "type": "step.started",
  "step_id": "step_4",
  "step_index": 4
}
```

结束：

``` json
{
  "type": "step.completed",
  "step_id": "step_4",
  "step_index": 4
}
```

这样客户端可以知道：

``` text
当前是第几个 Agent iteration
```

而不是只能看到一堆 token。

------------------------------------------------------------------------

## 7. Reasoning / 思考流

如果要实现类似 DeepSeek 的"思考过程"，建议不要把它混在普通文本流里面。

应该独立建模：

``` text
reasoning.delta
```

例如：

``` json
{
  "type": "reasoning.delta",
  "step_id": "step_4",
  "delta": "我先检查当前任务是否需要调用工具。"
}
```

然后：

``` json
{
  "type": "reasoning.delta",
  "step_id": "step_4",
  "delta": "接下来需要获取项目结构。"
}
```

完成：

``` json
{
  "type": "reasoning.completed",
  "step_id": "step_4"
}
```

核心设计：

``` text
Reasoning Stream
        │
        ├── delta
        └── completed

Answer Stream
        │
        ├── delta
        └── completed
```

不要设计成：

``` text
message.delta
  ├── thinking text
  └── answer text
```

否则前端很难区分"思考"和"最终答案"。

------------------------------------------------------------------------

## 8. Answer Stream

最终回答应该有独立的事件。

``` json
{
  "type": "message.delta",
  "message_id": "msg_123",
  "delta": "这是最终答案的第一部分"
}
```

继续：

``` json
{
  "type": "message.delta",
  "message_id": "msg_123",
  "delta": "这是第二部分。"
}
```

结束：

``` json
{
  "type": "message.completed",
  "message_id": "msg_123"
}
```

前端因此可以：

``` text
message.delta
    ↓
实时渲染最终答案
    ↓
message.completed
    ↓
结束 Markdown 渲染状态
```

------------------------------------------------------------------------

## 9. Tool Event

Tool 调用应该独立于 LLM 文本流。

``` text
tool.started
    ↓
tool.input
    ↓
tool.completed
```

例如：

``` json
{
  "type": "tool.started",
  "tool_call_id": "call_123",
  "tool_name": "search"
}
```

Tool 完成：

``` json
{
  "type": "tool.completed",
  "tool_call_id": "call_123",
  "tool_name": "search"
}
```

失败：

``` json
{
  "type": "tool.failed",
  "tool_call_id": "call_123",
  "error": {
    "code": "TIMEOUT"
  }
}
```

这样 UI 可以自然表现：

``` text
思考中...
  ↓
正在搜索...
  ↓
搜索完成
  ↓
继续思考...
```

------------------------------------------------------------------------

## 10. 推荐的完整事件流

一个典型 Agent Turn：

``` text
turn.started

step.started #1

reasoning.delta
reasoning.delta
reasoning.completed

tool.started
tool.completed

step.completed #1


step.started #2

reasoning.delta
reasoning.completed

message.delta
message.delta
message.completed

step.completed #2

turn.completed
```

这比单纯：

``` text
token
token
token
token
```

表达能力强很多。

------------------------------------------------------------------------

## 11. max_steps 与 SSE

如果 Agent 达到 max_steps：

``` text
step.completed #20
       ↓
Control
       ↓
MAX_STEPS
       ↓
turn.terminated
```

SSE：

``` text
event: step.completed
data: {"step_index":20}

event: turn.terminated
data: {
  "reason":"max_steps",
  "step_count":20
}
```

不要发送：

``` text
event: error
data: {"message":"max steps exceeded"}
```

因为：

``` text
MAX_STEPS ≠ SYSTEM ERROR
```

------------------------------------------------------------------------

## 12. Event Envelope

建议所有事件使用统一 Envelope。

``` json
{
  "id": "evt_123",
  "type": "reasoning.delta",
  "timestamp": "2026-08-21T13:00:00Z",

  "turn_id": "turn_123",
  "step_id": "step_4",
  "message_id": "msg_123",

  "data": {
    "delta": "..."
  }
}
```

其中：

``` text
id
    事件唯一 ID

type
    事件类型

timestamp
    事件时间

turn_id
    所属 Turn

step_id
    所属 Step

message_id
    所属 Message

data
    事件具体 payload
```

不需要每种事件都强制提供所有 ID。

例如 `turn.started` 不一定需要 `step_id`。

------------------------------------------------------------------------

## 13. Event ID 与断线恢复

SSE 天然存在断线问题。

因此建议事件具有单调递增或可恢复的 Event ID：

``` text
evt_100
evt_101
evt_102
evt_103
```

客户端断线后可以携带：

``` text
Last-Event-ID
```

服务端根据 Event ID 恢复。

因此：

``` text
Event ID
+
Event Store / Replay Buffer
```

是生产级 SSE 的重要组成部分。

如果暂时没有 replay 能力，至少保留唯一 Event ID，为后续演进留接口。

------------------------------------------------------------------------

## 14. Heartbeat

长时间没有业务事件时，需要 heartbeat 防止连接被中间层误判为断开。

例如：

``` text
: heartbeat
```

Heartbeat 是传输层机制，不应该污染业务事件模型。

因此：

``` text
heartbeat ≠ domain event
```

------------------------------------------------------------------------

## 15. Error 设计

错误应该分层。

### Tool Error

``` text
tool.failed
```

表示 Tool 执行失败。

### LLM Error

例如：

``` text
llm.failed
```

表示模型调用失败。

### Turn Error

``` text
turn.failed
```

表示 Turn 最终失败。

### Controlled Termination

例如：

``` text
turn.terminated
reason=max_steps
```

表示受控结束。

最终：

``` text
Failure
├── tool.failed
├── llm.failed
└── turn.failed

Termination
├── max_steps
├── timeout
├── max_tokens
└── cancelled
```

------------------------------------------------------------------------

## 16. 不建议把所有内部事件都暴露给 SSE

内部 Agent 可能有大量事件：

``` text
context.build.started
context.memory.lookup
skill.selected
prompt.rendered
llm.request.created
runtime.retry
...
```

这些事件可以存在于内部 Event Bus，但不一定全部暴露给客户端。

建议：

``` text
Internal Events
       │
       ↓
Event Filter / Projection
       │
       ↓
Public SSE Events
```

SSE 是 **Public Execution API**，不是内部 Debug Log。

------------------------------------------------------------------------

## 17. SSE 的三层模型

推荐最终形成：

``` text
             Agent Runtime
                   │
                   ↓
             Domain Events
                   │
                   ↓
          Event Projection
                   │
          ┌────────┴────────┐
          ↓                 ↓
      Public SSE        Observability
          │                 │
          ↓                 ↓
       Frontend         Logs / Traces
```

这样可以同时满足：

-   前端实时 UI
-   Agent 调试
-   日志
-   Trace
-   审计
-   后续 WebSocket / Webhook

------------------------------------------------------------------------

## 18. 最小可用事件集合

如果第一版不想设计太复杂，推荐先做：

``` text
turn.started
step.started
reasoning.delta
reasoning.completed
tool.started
tool.completed
message.delta
message.completed
step.completed
turn.completed
turn.terminated
turn.failed
```

这套已经可以支撑一个比较完整的 Agent UI。

------------------------------------------------------------------------

## 19. 推荐的完整生命周期

``` text
                    turn.started
                          │
                          ↓
                    ┌──────────┐
                    │ Step Loop│
                    └────┬─────┘
                         ↓
                    step.started
                         │
                         ↓
                  reasoning.delta
                         │
                         ↓
                ┌────────┴────────┐
                │                 │
              Tool             Answer
                │                 │
                ↓                 ↓
         tool.started       message.delta
                │                 │
         tool.completed      message.completed
                │                 │
                └────────┬────────┘
                         ↓
                    step.completed
                         │
                         ↓
                  Control Check
                         │
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
       Complete       Terminate        Error
          │              │              │
          ↓              ↓              ↓
 turn.completed   turn.terminated   turn.failed
```

------------------------------------------------------------------------

## 20. 最终设计原则

### 原则一：SSE 是事件流，不是 Token 流

``` text
SSE = Agent Execution Event Stream
```

### 原则二：Reasoning 和 Answer 分离

``` text
reasoning.delta
message.delta
```

不要混在一个文本流里。

### 原则三：Step 是核心执行单位

``` text
Turn
 └── Step
      ├── Reasoning
      ├── Tool
      └── Message
```

### 原则四：Termination 和 Failure 分离

``` text
turn.terminated
turn.failed
```

### 原则五：内部事件和公共事件分离

``` text
Internal Event
    ↓
Projection
    ↓
Public SSE
```

### 原则六：所有事件结构化

不要：

``` text
"Agent is thinking..."
```

而应该：

``` json
{
  "type": "reasoning.delta",
  "data": {
    "delta": "..."
  }
}
```

### 原则七：为 Replay / Resume 留接口

``` text
event_id
Last-Event-ID
Replay Buffer
```

------------------------------------------------------------------------

# 最终推荐架构

``` text
                         Agent Harness
                              │
          ┌───────────────────┼───────────────────┐
          ↓                   ↓                   ↓
       Context             Runtime             Control
                                                  │
                                            Termination
                                                  │
          └───────────────────┬───────────────────┘
                              ↓
                         Domain Events
                              │
                              ↓
                         Event Bus
                              │
                    ┌─────────┴─────────┐
                    ↓                   ↓
              Event Projection      Observability
                    │
                    ↓
               Public SSE
                    │
                    ↓
                 Frontend
```

这套设计的核心思想是：

> **Harness 负责产生 Agent 执行事件，Control 负责决定生命周期，SSE
> 负责把经过投影的执行事件可靠地实时传递给客户端。**
