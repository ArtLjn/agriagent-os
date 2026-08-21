# Agent Harness：max_steps Control 设计方法论

## 1. 设计目标

`max_steps` 不应该被设计成一个普通异常，而应该被视为 Agent Harness 中的
**Control / Termination Policy**。

核心原则：

> `max_steps` 表示 Agent 的计算预算耗尽，而不是系统发生故障。

因此：

``` text
max_steps ≠ error
max_steps = termination reason
```

------------------------------------------------------------------------

## 2. 在 Harness 中的位置

推荐将 `max_steps` 放在 Control 层：

``` text
Agent Harness
│
├── Context
│   ├── Context Build
│   ├── Memory
│   └── Skill
│
├── Runtime
│   ├── LLM
│   ├── Tool
│   └── Environment
│
└── Control
    ├── max_steps
    ├── timeout
    ├── max_tokens
    ├── max_tool_calls
    ├── cancellation
    └── termination policy
```

Control 层负责回答：

> Agent 是否还应该继续执行下一步？

而不是负责回答：

> Agent 具体应该做什么？

------------------------------------------------------------------------

## 3. Turn / Step / Termination 的关系

推荐把 Agent 执行抽象成：

``` text
Turn
 │
 ├── Step 1
 ├── Step 2
 ├── Step 3
 │    ...
 ├── Step N
 │
 └── Termination Policy
       │
       ├── COMPLETED
       ├── MAX_STEPS_REACHED
       ├── TIMEOUT
       ├── CANCELLED
       └── FAILED
```

其中：

-   **Turn**：一次完整的用户请求处理过程
-   **Step**：Agent 一次完整的 reasoning/action iteration
-   **Termination**：决定 Turn 是否继续
-   **max_steps**：限制 Step 数量

------------------------------------------------------------------------

## 4. max_steps 的语义

例如：

``` text
max_steps = 10
```

表示：

> 当前 Turn 最多允许 Agent 执行 10 个 Step。

正确执行：

``` text
Step 1
Step 2
...
Step 9
Step 10
  ↓
Termination Check
  ↓
MAX_STEPS_REACHED
  ↓
Turn End
```

不应该：

``` text
Step 10
  ↓
再调用 LLM 判断是否继续
  ↓
Step 11
```

否则 `max_steps` 就不再是一个严格的 hard limit。

------------------------------------------------------------------------

## 5. 为什么不应该直接 throw Error

当前设计：

``` python
if steps >= max_steps:
    raise MaxStepsError()
```

技术上可行，但语义上存在问题。

因为：

``` text
FAILED
```

通常意味着：

> 系统执行过程中发生了异常。

而：

``` text
MAX_STEPS_REACHED
```

意味着：

> 系统正常执行，但预算已经耗尽。

两者应该区分。

推荐：

``` text
COMPLETED
    ↓
任务正常完成

MAX_STEPS_REACHED
    ↓
受控终止，但任务可能未完成

FAILED
    ↓
系统或执行异常
```

------------------------------------------------------------------------

## 6. 推荐的状态模型

可以定义：

``` typescript
enum TurnStatus {
  RUNNING,
  COMPLETED,
  TERMINATED,
  CANCELLED,
  FAILED
}
```

然后通过 termination reason 进一步描述：

``` typescript
enum TerminationReason {
  COMPLETED,
  MAX_STEPS,
  TIMEOUT,
  MAX_TOKENS,
  MAX_TOOL_CALLS,
  CANCELLED,
  ERROR
}
```

最终状态：

``` typescript
interface TurnTermination {
  status: TurnStatus
  reason: TerminationReason
  stepCount: number
}
```

例如：

``` json
{
  "status": "TERMINATED",
  "reason": "MAX_STEPS",
  "stepCount": 20
}
```

------------------------------------------------------------------------

## 7. Control Loop 推荐设计

核心 Loop：

``` python
while True:

    if termination_policy.should_stop(context):
        return termination_policy.result()

    step = execute_step()

    update_context(step)

    if is_completed(step):
        return COMPLETED
```

更明确地：

``` text
                ┌───────────────┐
                │ Start Turn    │
                └───────┬───────┘
                        ↓
                ┌───────────────┐
                │ Control Check │
                └───────┬───────┘
                        │
             ┌──────────┴──────────┐
             │                     │
          should stop?           No
             │                     │
            Yes                    ↓
             │              ┌─────────────┐
             ↓              │ Execute Step│
        Termination         └──────┬──────┘
                                   ↓
                            Update Context
                                   │
                                   ↓
                            Check Completion
                                   │
                         ┌─────────┴─────────┐
                         ↓                   ↓
                      Complete             Continue
                         │                   │
                         ↓                   │
                      Finish ←───────────────┘
```

------------------------------------------------------------------------

## 8. max_steps 应该检查在哪里

推荐在 **Step 执行之前**进行硬限制检查。

``` python
if step_count >= max_steps:
    terminate(MAX_STEPS)
```

但有一个实现细节：

如果 `step_count` 表示"已经完成的 Step 数"，那么：

``` python
if step_count >= max_steps:
    stop
```

是最清晰的语义。

例如：

``` text
max_steps = 3

step_count = 0 → 执行 Step 1
step_count = 1 → 执行 Step 2
step_count = 2 → 执行 Step 3
step_count = 3 → STOP
```

这样不会产生 off-by-one 问题。

------------------------------------------------------------------------

## 9. max_steps 与其他限制统一

不要只为 `max_steps` 做一套机制。

推荐抽象：

``` text
TerminationPolicy
│
├── MaxStepsPolicy
├── TimeoutPolicy
├── TokenBudgetPolicy
├── ToolCallBudgetPolicy
└── CancellationPolicy
```

最终：

``` text
TerminationPolicy
        │
        ↓
   should_stop()
        │
   ┌────┴────┐
   │         │
  Yes        No
   │         │
Terminate   Continue
```

这样未来增加：

``` text
max_steps = 20
timeout = 60s
max_tokens = 100k
max_tool_calls = 50
```

不需要重构 Agent Loop。

------------------------------------------------------------------------

## 10. 与 Agent Completion 的优先级

建议明确优先级。

一个 Step 完成后：

``` text
Step completed
      ↓
是否满足任务完成条件？
      │
   Yes → COMPLETED
      │
     No
      ↓
是否触发 termination policy？
      │
   Yes → TERMINATED
      │
     No
      ↓
继续下一 Step
```

也就是说：

> 如果最后一个允许的 Step 已经完成任务，那么应该返回 `COMPLETED`，而不是
> `MAX_STEPS_REACHED`。

例如：

``` text
max_steps = 10

Step 10
  ↓
Agent 已经产生最终答案
  ↓
COMPLETED
```

而不是：

``` text
Step 10
  ↓
先判断 steps == max_steps
  ↓
MAX_STEPS_REACHED
```

这点非常重要。

------------------------------------------------------------------------

## 11. SSE 层的对应关系

Control 层产生 termination event：

``` json
{
  "type": "turn.terminated",
  "reason": "max_steps",
  "step_count": 20
}
```

而不是：

``` json
{
  "type": "error",
  "message": "max steps exceeded"
}
```

真正异常才产生：

``` json
{
  "type": "turn.failed",
  "error": {
    "code": "TOOL_EXECUTION_FAILED"
  }
}
```

------------------------------------------------------------------------

## 12. 用户体验

达到 max_steps 后，最终响应最好能够明确告诉用户：

``` text
任务未在最大执行步数内完成。
已执行 20 个步骤。
```

但不要把内部异常信息暴露给用户。

内部：

``` text
reason = MAX_STEPS
step_count = 20
```

用户：

``` text
任务因达到执行步数上限而停止，当前结果可能不完整。
```

------------------------------------------------------------------------

## 13. 推荐最终模型

``` text
                    Turn
                     │
                     ↓
                Agent Loop
                     │
                     ↓
              ┌──────────────┐
              │ Control      │
              │              │
              │ max_steps    │
              │ timeout      │
              │ token budget │
              │ cancellation │
              └───────┬──────┘
                      ↓
              TerminationPolicy
                      │
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
    COMPLETED      TERMINATED      FAILED
                     │
              ┌──────┼───────┐
              ↓      ↓       ↓
          MAX_STEPS TIMEOUT CANCELLED
```

## 14. 核心结论

`max_steps` 的正确定位是：

> **Agent Harness 的执行预算控制器，而不是异常处理器。**

最终推荐：

``` text
max_steps
    ↓
Control
    ↓
Termination Policy
    ↓
MAX_STEPS_REACHED
    ↓
Turn Terminated
    ↓
SSE turn.terminated
```

同时保证：

1.  `max_steps` 是硬上限
2.  不因 max_steps 直接抛系统 Error
3.  与 `timeout / token / tool calls` 统一为 Budget / Termination
    Control
4.  `COMPLETED` 与 `MAX_STEPS_REACHED` 明确区分
5.  SSE 通过 termination event 表达受控终止
6.  真正异常才进入 `FAILED`
