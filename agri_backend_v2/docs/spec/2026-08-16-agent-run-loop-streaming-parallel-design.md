---
spec_id: 2026-08-16-agent-run-loop-streaming-parallel-design
last_updated: 2026-08-16
status: proposed
---

# v2 Agent Run Loop、并行 Skill 与流式事件设计

> 目标：把 v2 Agent 分散在 Worker、ReAct、Skill 加载、Tool 执行和 SSE 中的职责整理成可读、可验证、可逐步迁移的 Harness 设计。
>
> 适用范围：v2/agent 的 Turn 执行、Skill 注册、ReAct 循环、并行 Tool 调度、HITL 等待、SSE/Redis 事件和终态收口。
>
> 关联设计：2026-08-12-agent-chat-concurrency-harness、2026-08-08-agent-intent-convergence-fix、2026-08-10-agent-hitl-approval-state-repair。

## 1. 结论摘要

当前 v2 已具备主要 Harness 零件，但边界没有显式表达：

~~~text
Redis Worker 生命周期
  + ReAct 决策循环
  + Tool/Skill 校验与执行
  + Plan 执行
  + HITL 等待
  + SSE 事件发布
  + 最终答复收口
~~~

主要问题：

1. LLM 可以返回多个 tool_calls，但 Runtime 在 dispatch 中逐个串行执行。
2. chat_stream 已产生 token 和 Tool Call 增量，但 react.py 缓冲后才继续，用户看不到循环中的实时进度。
3. action 事件在 Skill 执行完成后才真正发送，耗时调用期间没有“正在执行”消息。
4. final_answer_delta 已定义但没有接通主链路。
5. max_steps 只是安全预算，却被当成失败收口机制；达到预算时可能只有错误和 done，没有用户可读答复。
6. 当前已有 doom_loop 局部检测，但重复调用、不可重试 Tool 错误和 MCP 断流尚未统一进入 Finalizer，部分链路仍可能继续消耗预算。
7. System Reminder 要求模型调用 final_answer，但 final_answer 不是注册给模型的 Tool，形成协议冲突。
8. loader.load_all 实际已经承担 Skill Registry 职责，却只返回列表，调用方再手动构造 skill_index。

核心决策：

- SkillLoader 表示文件系统加载，SkillRegistry 表示运行时能力索引。
- TurnRunner 管理一轮生命周期，ReActLoop 管理 Reason → Act → Observe。
- ToolBatchExecutor 处理同一 LLM 响应中的并行/串行 Tool 调度。
- ProgressPublisher 统一实时事件、心跳、重试和终态事件。
- max_steps 只作为安全上限，所有预算、重复、超时和中断路径都必须进入 TurnFinalizer。
- 并行 Skill 与 Turn 并发是两种独立容量。Redis 的 Turn 并发上限不等于单个 Turn 内的 Skill 并发上限。

## 2. 现状与问题证据

### 2.1 当前调用链

~~~mermaid
flowchart TD
    A[POST /api/v2/chat] --> B[创建 durable Turn]
    B --> C[Redis dispatch stream]
    C --> D[Worker _run_turn]
    D --> E[react.run_turn]
    E --> F[Setup Context 和 Skills]
    F --> G[while step_count < max_steps]
    G --> H[LLM chat_stream]
    H --> I{是否有 tool_calls}
    I -->|否| J[Finalizer]
    I -->|是| K[ToolBatchExecutor]
    K --> L[参数校验和 HITL]
    L --> M[Skill 执行]
    M --> N[Observation]
    N --> G
    K --> O[make_plan]
    O --> P[Plan Executor]
    P --> M
    J --> Q[Redis Event Stream]
    Q --> R[SSE 客户端]
~~~

### 2.2 循环分类

| 循环 | 当前入口 | 职责 | 预算/终止 |
|---|---|---|---|
| Worker Loop | worker._worker_loop | 消费 Redis Turn、回收未确认消息 | Worker stop、Redis 错误 |
| Turn Loop | worker._run_turn | 租约、超时、取消、持久化和事件发布 | Turn execution timeout |
| ReAct Loop | react.run_turn 内部 while | LLM 决策、Tool 执行、Observation 回灌 | step、token、doom、cancel |
| Tool Batch Loop | 当前 dispatch | 执行一次 assistant response 的多个 Tool Call | 批次数量、信号量 |
| Plan Loop | 当前 execute_plan_steps | 执行 make_plan 的步骤 | 步骤数、依赖、失败策略 |

当前多个循环通过 Turn 的 status、finalization_pending、committed_result 和 pending_approval 传递控制。本设计保留 Turn 作为持久化事实载体，但增加显式运行阶段和停止原因。

### 2.3 当前流式缺口

底层 llm.py 已经产生 text、tool_call、done 和 error 增量，但 react.py 的 LLM 适配只累积结果。

~~~text
LLM 生成期间       无实时用户消息
Tool 参数生成期间  无实时用户消息
Tool 执行期间      action 事件发送偏晚
最终回答生成期间   一次性发送完整文本
~~~

Redis 事件流可以重放，但 turn_store 当前没有 heartbeat/progress 语义。后端调用耗时或 Worker 异常时，客户端可能看到空白等待。

## 3. 设计原则

### 3.1 模型负责弹性决策，Runtime 负责确定性边界

模型可以决定下一步想调用哪个 Tool，但不能决定：

- 是否绕过 HITL；
- 是否执行未注册 Tool；
- 是否并行执行写操作；
- 是否在错误后继续调用无关 Tool；
- 是否无限循环；
- 是否把没有提交的结果说成已完成。

### 3.2 流式输出是事件协议

用户需要知道当前阶段和可验证结果，不需要接收未经处理的内部推理。事件必须区分：

- 模型生成增量；
- Tool Call 解析增量；
- Tool 开始和完成；
- 等待审批、重试和进度；
- 最终答复增量；
- 终态。

### 3.3 并行必须有能力声明和资源边界

模型一次返回多个 Tool Call 不代表它们天然可以并行。并行策略由 Skill 元数据、参数依赖和运行时信号量共同决定。

### 3.4 任何路径都必须有终态

一个 Turn 最终必须产生：

~~~text
final_answer（成功或用户可读失败答复）
  + done(status=completed|failed|rejected|cancelled|timeout)
~~~

不允许因流超时、max_steps、Worker 异常或重连而只有半截事件、无答复或无 done。

## 4. 目标架构

~~~mermaid
flowchart LR
    subgraph API[Agent API]
        Chat[POST /api/v2/chat]
        Events[GET /turns/{id}/events]
        Approve[POST /api/v2/approve]
    end

    subgraph Coordination[持久化协调层]
        Dispatch[(Redis dispatch stream)]
        TurnStore[(Redis Turn state)]
        EventStore[(Redis event stream)]
        Approval[(Redis approval state)]
    end

    subgraph Runtime[Agent Runtime]
        Worker[TurnWorker]
        Runner[TurnRunner]
        State[TurnStateMachine]
        Context[ContextAssembler]
        Loop[ReActLoop]
        Registry[SkillRegistry]
        Batch[ToolBatchExecutor]
        Policy[ExecutionPolicy]
        Publisher[ProgressPublisher]
        Finalizer[TurnFinalizer]
    end

    subgraph Providers[外部能力]
        LLM[LLM Provider]
        MCP[Business MCP]
    end

    Chat --> Dispatch
    Approve --> Approval
    Dispatch --> Worker
    Worker --> Runner
    Runner --> State
    Runner --> Context
    Runner --> Loop
    Loop --> LLM
    Loop --> Batch
    Registry --> Batch
    Policy --> Batch
    Batch --> MCP
    Batch --> Publisher
    State --> TurnStore
    Publisher --> EventStore
    Finalizer --> Publisher
    EventStore --> Events
    Approval --> Runner
~~~

| 模块 | 目标文件 | 只负责什么 | 不负责什么 |
|---|---|---|---|
| TurnWorker | infra/worker.py | Redis 消费、租约、调用 TurnRunner | LLM 决策、Skill 选择 |
| TurnRunner | runtime/turn_runner.py | 一轮生命周期和资源组装 | 具体 Tool 分发 |
| TurnStateMachine | runtime/turn_state.py | 阶段转换、终态和停止原因 | 生成自然语言 |
| ContextAssembler | core/context.py | System、Memory、消息和 reminder | 执行 Tool |
| ReActLoop | core/react_loop.py | Reason → Tool Batch → Observe | Redis 租约和 HTTP |
| SkillLoader | skills/loader.py | 目录、YAML、Python 模块加载 | 按名称查找和执行策略 |
| SkillRegistry | skills/registry.py | Skill 索引、Schema、能力元数据 | 执行 Skill、等待审批 |
| ToolBatchExecutor | core/tool_batch.py | 批次校验、并发、结果汇聚 | 决定业务写入是否批准 |
| ExecutionPolicy | core/execution_policy.py | 决定串行/并行和并发上限 | 调用 LLM |
| ProgressPublisher | infra/progress.py | 实时事件、心跳、重试和 Redis 发布 | 修改业务状态 |
| TurnFinalizer | core/finalizer.py | 成功、失败、预算耗尽和提交后收尾 | 继续调用业务 Tool |

初期保留兼容入口 react.run_turn，内部委托给 TurnRunner.run。兼容入口只负责适配，不再增加业务分支。

## 5. 函数和类命名规范

### 5.1 Skill 加载与 Registry

当前 load_all 名称过于宽泛，而且返回列表导致调用方重复构造字典。目标接口：

~~~python
class SkillLoader:
    """从技能目录加载 Skill 实例。"""

    def discover_skill_dirs(self) -> list[Path]: ...
    def load_skill_dir(self, skill_dir: Path) -> Skill | None: ...
    def load_all(self) -> list[Skill]: ...


class SkillRegistry:
    """Turn 内只读的 Skill 能力索引。"""

    @classmethod
    def from_directory(cls, skills_dir: Path) -> "SkillRegistry": ...

    @classmethod
    def from_skills(cls, skills: Iterable[Skill]) -> "SkillRegistry": ...

    def get(self, name: str) -> Skill | None: ...
    def require(self, name: str) -> Skill: ...
    def all(self) -> tuple[Skill, ...]: ...
    def exposed(self) -> tuple[Skill, ...]: ...
    def exposed_tools(self) -> list[dict[str, Any]]: ...
    def capabilities(self, name: str) -> SkillCapabilities: ...
    def validate(self) -> None: ...
~~~

| 不推荐 | 推荐 | 原因 |
|---|---|---|
| load_dir | load_skill_dir | 明确加载对象是 Skill 目录 |
| load_all 作为业务入口 | SkillRegistry.from_directory | 业务方不应知道扫描细节 |
| find_skill(skills, name) | registry.get(name) | 查找属于 Registry |
| to_openai_tools(skills) | registry.exposed_tools() | Schema 是 Registry 的公开视图 |
| skill_index | skill_registry | 避免调用方维护第二个索引 |
| skill.execute 直接散落调用 | ToolExecutor.execute | 统一参数、策略、事件和错误边界 |

SkillLoader 可以保留 load_all 作为内部兼容函数，但不再由 react.py 直接调用。

### 5.2 ReAct 和 Turn 生命周期

~~~python
class TurnRunner:
    async def run(self, turn: Turn) -> AsyncIterator[AgentEvent]: ...


class ReActLoop:
    async def run(self, context: TurnRuntime) -> AsyncIterator[AgentEvent]: ...
    async def run_reasoning_step(self, context: TurnRuntime) -> StepOutcome: ...


class ToolBatchExecutor:
    async def execute_batch(
        self,
        calls: Sequence[ToolCall],
        context: TurnRuntime,
    ) -> ToolBatchResult: ...

    async def execute_one(
        self,
        call: ToolCall,
        context: TurnRuntime,
    ) -> ToolResult: ...


class TurnFinalizer:
    async def finalize_success(
        self,
        context: TurnRuntime,
    ) -> AsyncIterator[AgentEvent]: ...

    async def finalize_failure(
        self,
        context: TurnRuntime,
        reason: StopReason,
    ) -> AsyncIterator[AgentEvent]: ...

    async def finalize_budget_exhausted(
        self,
        context: TurnRuntime,
    ) -> AsyncIterator[AgentEvent]: ...
~~~

| 当前名称 | 目标名称 | 迁移说明 |
|---|---|---|
| _setup_turn_runtime | build_turn_runtime | 返回结构化 TurnRuntime，不返回五元组 |
| _run_single_reasoning_step | run_reasoning_step | 一次 LLM 决策和结果分类 |
| _call_llm_stream | stream_llm_decision | LLM 流解析和 Trace |
| _dispatch_tool_calls | execute_tool_batch | 明确这是一个批次，不默认串行 |
| _process_skill_call | prepare_tool_call + execute_tool_call | 校验和执行分开 |
| _run_skill_call | execute_tool_call | 统一单 Tool 执行入口 |
| _apply_approval_gate | request_tool_approval | 产生审批请求，不包含执行 |
| _handle_make_plan | execute_plan_request | make_plan 是一种执行模式 |
| _execute_plan_steps | execute_plan | 根据依赖图选择串/并行 |
| _finalize_turn | finalize_turn | 所有未收口路径经过它 |
| _persist_memory | persist_completed_turn | 仅保存闭合结果 |

### 5.3 状态和停止原因

TurnStatus 表示持久化业务状态；TurnPhase 表示 Runtime 阶段，不能混用：

~~~python
class TurnPhase(str, Enum):
    SETUP = "setup"
    REASONING = "reasoning"
    TOOL_PREPARING = "tool_preparing"
    TOOL_EXECUTING = "tool_executing"
    AWAITING_APPROVAL = "awaiting_approval"
    OBSERVING = "observing"
    FINALIZING = "finalizing"
    TERMINAL = "terminal"


class StopReason(str, Enum):
    MODEL_COMPLETED = "model_completed"
    STEP_BUDGET_EXHAUSTED = "step_budget_exhausted"
    TOKEN_BUDGET_EXHAUSTED = "token_budget_exhausted"
    DOOM_LOOP_DETECTED = "doom_loop_detected"
    LLM_FAILED = "llm_failed"
    TOOL_FAILED = "tool_failed"
    APPROVAL_REJECTED = "approval_rejected"
    APPROVAL_EXPIRED = "approval_expired"
    USER_CANCELLED = "user_cancelled"
    TURN_TIMEOUT = "turn_timeout"
    PIPELINE_CRASH = "pipeline_crash"
~~~

## 6. SkillRegistry 和能力元数据

### 6.1 Registry 责任

SkillRegistry 是单个 Turn 读取的稳定能力视图，负责：

- 按名称索引基础 Skill 和 OperationSkill；
- 暴露面向模型的 Tool Schema；
- 区分 expose_to_model=false 的内部后继动作；
- 校验名称、Schema、MCP tool 和 operation 展开结果；
- 提供风险、是否可并行、是否有依赖和是否成功后收尾等能力元数据。

Registry 不负责执行 Skill、等待审批、生成 SSE、重试 Business 请求或直接修改 Turn 状态。

### 6.2 Skill 元数据扩展

现有字段保持兼容，新增字段建议放在 skill.md YAML front matter：

~~~yaml
name: get_farm_status
description: 查询当前农场经营概况
kind: mcp
risk_level: read
execution:
  mode: parallel_safe
  max_concurrency: 4
  requires_observation: false
  depends_on: []
completion:
  finalize_after_success: true
~~~

允许的 execution.mode：

| 值 | 含义 |
|---|---|
| serial | 必须单独或顺序执行，默认值 |
| parallel_safe | 与同批其他 parallel_safe Tool 可并行 |
| serial_after_observation | 必须等待前一批 Observation |
| internal_followup | 不能直接暴露给模型，由 Runtime 驱动 |

缺少 execution 配置时按 serial 处理，不因迁移而意外并行写操作。

### 6.2.1 Skill YAML 并行契约

`execution` 是 Skill 能力声明，不是模型提示词。Runtime 必须在 Registry 构建时将它解析成不可变的 `ExecutionPolicy`；模型不能通过参数或自然语言改变该策略。

顶层 Skill 的标准写法如下：

~~~yaml
execution:
  mode: serial                 # serial | parallel_safe | serial_after_observation | internal_followup
  max_concurrency: 1           # 仅 parallel_safe 有效；必须为正整数
  requires_observation: false  # true 时不得与依赖它的调用同批执行
  depends_on: []               # Tool 名称或资源键，首期只允许声明性校验
completion:
  finalize_after_success: false
~~~

约束如下：

| 配置 | 约束 | 运行时语义 |
|---|---|---|
| 缺少 `execution` | 合法 | 等价于 `mode: serial` |
| `read + parallel_safe` | 合法 | 可进入同一批次的有界并行队列 |
| `write_confirm/write_high + parallel_safe` | 启动失败 | 禁止把写操作声明为并行安全 |
| `mixed + parallel_safe` | 启动失败 | 必须拆成 operation 级 Skill |
| `serial_after_observation` | 合法 | 必须等待前一批 Observation 后再执行 |
| `internal_followup` | 合法 | 不暴露给模型，只能由 Runtime 驱动 |
| `max_concurrency` | 缺省为 1，并受全局 `max_parallel_skills` 再次限制 | 实际上限为两者较小值 |
| `depends_on` | 引用未知 Tool、自己依赖自己或形成环 | Registry 启动校验失败 |

聚合 MCP Skill 的 operation 必须支持局部覆盖，覆盖优先级为：

~~~text
operation.execution / operation.completion
  > skill.execution / skill.completion
  > Runtime 默认值（serial / finalize_after_success=false）
~~~

例如作物茬口查询可以明确声明只读并行，写操作保持串行：

~~~yaml
operations:
  templates:
    tool_name: list_crop_templates
    risk_level: read
    execution:
      mode: parallel_safe
      max_concurrency: 4
      requires_observation: false
      depends_on: []
  system_templates:
    tool_name: list_system_crop_templates
    risk_level: read
    execution:
      mode: parallel_safe
      max_concurrency: 4
      requires_observation: false
      depends_on: []
  create:
    tool_name: create_crop_cycle
    risk_level: write_confirm
    execution:
      mode: serial
~~~

`system_templates` 不默认声明 `finalize_after_success`：同一查询既可能是用户最终要看的结果，也可能只是后续导入/创建的前置事实。是否可以在查询成功后收尾，必须由任务范围或明确的 completion 能力决定，不能仅根据 `read` 或 `parallel_safe` 推断。

`OperationSkill` 必须把 operation 的 `execution` 和 `completion` 投影到最终能力对象；只复制 `risk_level` 而忽略并行元数据属于 Registry 契约错误。Registry 对所有最终暴露的 operation 执行一次统一校验，并在失败时返回包含 `code`、Skill 名称和 operation 名称的启动错误。

### 6.3 Registry 构建校验

必须检查：

- 公开 Tool 名称不能重复；
- 内部 follow-up 名称不能覆盖公开 Tool；
- parameters.required 必须存在于 parameters.properties；
- kind=local 必须存在可导入实现；
- MCP Skill 必须声明目标 MCP tool；
- parallel_safe Skill 不能声明非幂等写风险；
- approval_followup 目标必须是 internal_followup；
- finalize_after_success 只能用于返回完整事实结果的 Skill。

校验失败必须返回带 code 和 Skill 名称的启动错误，不允许静默跳过。

## 7. Tool Batch 并行设计

### 7.1 批次语义

一条 assistant message 中的多个 Tool Call 构成一个 ToolBatch：

~~~text
assistant(tool_call_1, tool_call_2, tool_call_3)
  -> prepare all calls
  -> classify execution policy
  -> execute independent parallel-safe calls
  -> execute serial calls in declared order
  -> append one tool result per tool_call_id
  -> return one aggregated observation
~~~

所有 Tool Result 必须保留 tool_call_id。并行完成顺序可以不同，但写回消息历史时按原始 Tool Call 顺序排列。

### 7.2 调度算法

~~~mermaid
flowchart TD
    A[收到 assistant tool_calls] --> B[解析和校验 tool_call_id]
    B --> C{存在 make_plan?}
    C -->|是| D[进入 Plan Executor]
    C -->|否| E[读取 SkillRegistry 能力]
    E --> F[参数、重复、审批和状态检查]
    F --> G{parallel_safe 且无依赖?}
    G -->|是| H[进入有界并行批次]
    G -->|否| I[进入串行队列]
    H --> J[逐个发布 tool_started/tool_finished]
    I --> J
    J --> K[按原始顺序生成 Tool Result]
    K --> L[追加 observation]
    L --> M[回到 ReAct Loop]
~~~

~~~python
async def execute_batch(
    calls: list[ToolCall],
    runtime: TurnRuntime,
) -> ToolBatchResult:
    prepared = [
        await prepare_tool_call(call, runtime)
        for call in calls
    ]
    parallel, serial = split_by_execution_policy(
        prepared,
        runtime.registry,
    )

    parallel_results = await bounded_gather(
        parallel,
        limit=runtime.config.max_parallel_skills,
        execute=execute_tool_call,
    )

    serial_results = []
    for call in serial:
        serial_results.append(
            await execute_tool_call(call, runtime)
        )

    return ToolBatchResult.in_original_call_order(
        [*parallel_results, *serial_results],
        calls,
    )
~~~

bounded_gather 必须满足：

- 使用 asyncio.Semaphore 或等价有界调度；
- 单个 Tool 失败只标记该 Tool 失败，不能静默丢失其他结果；
- 不因一个可恢复只读错误取消整个批次；
- 取消、Turn 超时或审批拒绝时取消未完成任务；
- 每个 Tool 都有独立开始、完成、失败 Trace；
- 结果消息按原始 Tool Call 顺序写入；
- Skill 并发数与 Redis Worker/Turn 并发数分别配置。

默认所有 write_confirm、write_high 和不明风险 Skill 都按串行处理。写调用必须经过 HITL，同一批次内多个写调用不得自动并行提交。prepare → approval → commit follow-up 必须由 Runtime 驱动。

首期只支持同一 assistant response 中独立只读 Tool Call 的并行。make_plan 仍按顺序执行。未来 Plan 并行必须增加 depends_on 和 execution_mode，只有依赖完成、风险允许且资源有余量的 Step 才能进入下一批。

## 8. 循环中的流式输出

### 8.1 四层语义

| 层级 | 事件 | 默认可见 | 作用 |
|---|---|---:|---|
| LLM 生成层 | reasoning_delta、tool_call_delta | 受控 | 表示模型仍在生成 |
| Tool 执行层 | tool_started、tool_finished | 是 | 告知正在做什么以及结果 |
| Runtime 进度层 | progress、heartbeat、retrying | 是 | 防止长时间空白 |
| 答复层 | final_answer_start、final_answer_delta、final_answer | 是 | 展示最终答复 |

不要把带 Tool Call 的模型文本直接当最终答案，也不应默认把完整内部推理原文发送给用户。

### 8.2 正常事件顺序

~~~text
meta
started
reasoning_started
reasoning_delta* / tool_call_delta*
tool_started
heartbeat*
tool_finished
observation
reasoning_started
final_answer_start
final_answer_delta*
final_answer
done(status=completed)
~~~

并行批次中，tool_started/tool_finished 可以交错，但每个事件必须包含 turn_id、tool_call_id、tool_name、step 和 seq。

### 8.3 心跳

心跳不是伪造进度：

~~~json
{
  "type": "heartbeat",
  "data": {
    "phase": "tool_executing",
    "message": "正在等待业务查询结果",
    "elapsed_ms": 12000
  }
}
~~~

建议每 5-15 秒发送一次。进入 awaiting_approval 时发送明确等待状态，不用 heartbeat 代替审批事件。

Redis Stream 约束：

- seq 单调递增；
- after_seq 重连不会重新执行 Turn；
- 终态事件只写一次；
- Worker 崩溃后，重连能看到最后一个已持久化事件；
- stream_events 到达等待上限时不能静默结束；
- Turn 未终态时，必须发布 stream_timeout 或由清理器生成 timeout；
- 事件保留时间不短于客户端最大重连窗口。

## 9. Run Loop 终止和优雅收口

### 9.1 显式状态机

~~~mermaid
stateDiagram-v2
    [*] --> Setup
    Setup --> Reasoning
    Reasoning --> ToolPreparing: 收到 tool_calls
    Reasoning --> Finalizing: 无 tool_calls
    ToolPreparing --> ToolExecuting: 参数和策略通过
    ToolPreparing --> AwaitingApproval: 需要审批
    ToolPreparing --> Finalizing: 不可恢复错误
    AwaitingApproval --> ToolExecuting: approved
    AwaitingApproval --> Finalizing: rejected/expired/cancelled
    ToolExecuting --> Observing: 返回 Tool Result
    ToolExecuting --> Finalizing: 终止性错误
    Observing --> Reasoning: 仍有预算
    Observing --> Finalizing: finalize_after_success
    Reasoning --> Finalizing: doom/step/token/timeout
    Finalizing --> Completed
    Finalizing --> Failed
    Finalizing --> Rejected
    Finalizing --> Cancelled
    Finalizing --> Timeout
    Completed --> [*]
    Failed --> [*]
    Rejected --> [*]
    Cancelled --> [*]
    Timeout --> [*]
~~~

### 9.2 终止优先级

1. 用户取消、Turn 超时和进程取消：立即停止可取消任务；
2. Business 已提交：不得报告为失败，进入确定性成功收尾；
3. HITL 拒绝或过期：停止当前写链路；
4. 不可重试业务错误：停止相关 Tool 链路；
5. Doom Loop：停止相同调用模式；
6. Token 超限：先压缩 Context，失败则收口；
7. Step budget：执行一次无 Tool 收尾或确定性摘要；
8. LLM 无 Tool 文本：正常完成。

### 9.3 max_steps 处理

~~~text
emit progress(code=step_budget_exhausted)
  -> 如果 committed_result 存在：确定性成功答复
  -> 否则：一次无 Tool、低预算的摘要收尾
  -> 摘要失败：基于最近 observation 生成确定性失败答复
  -> update Turn(status=failed, error_code=step_budget_exhausted)
  -> emit error(code=step_budget_exhausted)
  -> emit final_answer
  -> emit done(status=failed)
~~~

摘要收尾不得重新暴露业务写 Tool。若没有可靠 Observation，答复必须明确“尚未完成”，不能推断业务成功。

### 9.4 重复调用和无进展收口

重复调用不是普通的 Tool 重试，而是 ReAct Loop 没有产生新进展。Runtime 必须在执行前、且在参数 enrich 和默认值展开之后，记录一次 `ProgressLedger`：

~~~json
{
  "call_key": "list_system_crop_templates|{\"category\":null,\"limit\":50,\"skip\":0}",
  "observation_fingerprint": "sha256:...",
  "tool_name": "list_system_crop_templates",
  "attempt": 3,
  "progress": "unchanged"
}
~~~

其中：

- `call_key` 使用稳定 JSON、排序后的字段和业务默认值；不能让 `{}` 与服务端默认分页参数绕过重复检测。
- `observation_fingerprint` 忽略时间、耗时、请求 ID、Trace ID 等易变字段；相同调用但结果确实变化时，不得误判为死循环。
- `progress=advanced` 表示得到新事实或业务状态发生变化；`unchanged` 表示相同请求得到等价结果；`blocked` 表示结构化错误明确不可继续。

处理规则：

1. 首次调用正常执行并把结果作为 Observation 写入消息历史。
2. 第二次相同调用只产生一次 `verification_warning`，Observation 必须明确提示“已有结果，先基于现有结果回答；只有改变业务参数或补充信息后才能再次查询”。
3. 达到默认阈值 3 次，Runtime 立即设置 `StopReason.DOOM_LOOP_DETECTED`，取消该 Turn 尚未开始的工具任务，不再请求下一次 LLM。
4. doom 收口必须保留最后一次 Observation，并由 Finalizer 生成用户可读答复；不得用“请换一个 Skill”把决策再次交给模型，也不得继续跑到 `max_steps`。
5. 不同参数只有在参数确实改变查询范围时才算新进展；仅改变无效分页、空参数或等价默认值不能绕过阈值。若无法证明参数语义等价，宁可按不同调用执行，但仍受 `no_progress` 和总步数保护。

doom、不可重试错误和 `max_steps` 的区别必须在 Trace、Redis 状态和 SSE 中保持一致：

| 情况 | `stop_reason` | 是否再次请求 LLM | 最终答复重点 |
|---|---|---:|---|
| 相同调用和结果达到阈值 | `doom_loop_detected` | 否 | 已尝试的 Tool、次数、最后结果和缺失信息 |
| 参数/业务永久错误 | `tool_failed` 或具体错误原因 | 仅在存在声明的安全 fallback 时 | Tool 返回的明确原因 |
| MCP/LLM 瞬时错误 | 重试耗尽后的具体原因 | 只允许有界重试 | 重试次数和最终故障 |
| 达到步数上限且没有更具体原因 | `step_budget_exhausted` | 只允许一次无 Tool 收尾 | 尚未完成，不能推断成功 |

统一终态序列为：

~~~text
warning/observation（可选）
  -> finalizing
  -> error（失败终态需要）
  -> final_answer_start
  -> final_answer_delta*
  -> final_answer
  -> done(status=...)
~~~

`TurnFinalizer` 是唯一负责发出 `final_answer` 和 `done` 的组件。现有 `_emit_doom_loop_terminal`、Pipeline 异常兜底和 Worker 超时处理迁移后只能提交 `FinalizationRequest`，不能各自拼接终态事件。

final_answer 不是模型 Tool。模型正常完成的定义是返回无 tool_calls 的文本。Prompt 和 Reminder 必须使用“返回最终文本”或“停止调用工具并回答”，不能要求模型调用不存在的 final_answer Tool。

## 10. 错误、重试和消息交付

| 错误 | 是否重试 | Run Loop 行为 | 用户事件 |
|---|---:|---|---|
| LLM 连接前失败 | 有界 | 重试并保留阶段 | retrying |
| LLM 已开始输出后断流 | 默认不重试当前流 | 终止或重新发起新 Turn | error + done |
| MCP 临时网络错误 | 有界 | 返回带 code 的 Tool Result | retrying/tool_finished |
| 参数缺失 | 否 | 返回 observation，必要时追问 | progress 或最终追问 |
| 未知 Tool | 否 | 立即停止该调用 | error(code=unknown_tool) |
| 业务不可重试错误 | 否 | 停止相关写链路 | error + 最终答复 |
| 审批过期/拒绝 | 否 | 进入拒绝或超时终态 | approval_result + done |
| Context 超限 | 压缩一次 | 成功则继续，失败则收口 | context_compressing |
| Step budget | 否 | 进入 Finalizer | progress + final_answer + done |

Tool 错误要进入模型 Observation，但 Runtime 错误和终态错误不能只作为字符串返回。错误至少包含：

~~~json
{
  "code": "tool_timeout",
  "message": "业务查询超过 30 秒",
  "phase": "tool_executing",
  "tool_name": "get_weather",
  "retryable": false
}
~~~

TurnFinalizer 是唯一可以发出 final_answer 和 done 的组件。Worker 的异常兜底只能调用 Finalizer，不能自己拼另一套终态事件。

Tool 结果的 `retryable=false` 不能只停留在事件字段中。普通 Tool 后处理必须根据结果分类：可恢复错误进入 Observation 供模型调整；不可恢复错误进入 `FinalizationRequest`；只有 Registry 声明的 fallback 才允许继续执行替代 Tool。模型不能因为看到了一个错误，就自由选择另一个写操作。

## 11. 实施范围

### 11.1 P0：契约和终态修复

- 新增 SkillRegistry，保留 loader 兼容入口；
- 修正 final_answer Prompt/Runtime 契约；
- 引入 StopReason 和显式 TurnPhase；
- 统一 max_steps、doom、超时、取消和不可重试错误收口；
- 所有路径都有用户可读答复以及 done。

### 11.2 P1：循环中的流式输出

- 将 LLM text/tool_call 增量转为受控事件；
- Tool 执行前立即发送 tool_started；
- Tool 完成后发送 tool_finished；
- 接通 final_answer_delta；
- 增加 heartbeat、progress、retrying；
- 修复事件流等待超时的静默结束。

### 11.3 P2：同一 assistant response 的并行 Skill

- 新增 ToolBatchExecutor；
- 仅允许显式声明 parallel_safe 的 Skill 并行；
- 只读查询优先支持并行；
- 增加单 Turn 内 max_parallel_skills 信号量；
- 保持 tool_call_id 和原始顺序；
- 支持单个 Tool 失败而其他 Tool 正常完成；
- 写操作、审批 follow-up 和未知能力默认串行。

### 11.4 P3：文件职责迁移

- 将 react.py 拆为 ReActLoop、ToolBatchExecutor、TurnFinalizer 和运行时结构；
- 保留 react.run_turn 兼容入口；
- worker.py 不再理解 ReAct 具体分支；
- planner.py 不再依赖 react.py 私有函数名。

### 11.5 非目标

- 不修改 Business MCP 协议和业务事务语义；
- 不改变 /api/v2/chat、/approve 和 SSE URL；
- 不把 MCP 工具直接暴露给前端；
- 不实现任意写 Skill 的自动并行；
- 不在首期把 make_plan 改造成完整 DAG/BPMN 引擎；
- 不新增关键词路由、确认词库或第二套 SkillRouter；
- 不把完整内部思维链默认发送给用户；
- 不把 Redis Turn 并发上限解释成 Skill 吞吐承诺；
- 不顺手修复无关的前端或业务接口问题。

## 12. 预期文件边界

~~~text
v2/agent/skills/registry.py
v2/agent/skills/loader.py
v2/agent/skills/base.py
v2/agent/core/turn.py
v2/agent/core/context.py
v2/agent/core/react.py
v2/agent/core/react_loop.py
v2/agent/core/tool_batch.py
v2/agent/core/finalizer.py
v2/agent/infra/progress.py
v2/agent/infra/sse.py
v2/agent/infra/turn_store.py
v2/agent/infra/worker.py
v2/agent/skills/*/skill.md
v2/tests/
~~~

新文件必须有清晰边界，不能为绕过复杂度检查拆成大量碎片。react.py 的拆分应以“一个模块一个完整职责”为依据。

## 13. 验收标准

> 说明：`[x]` 仅表示当前代码已有 focused test 或明确的运行时证据；只有设计描述、静态代码存在或尚未完成真实链路验证的项目保持 `[ ]`。

### 13.1 Registry

- [x] SkillRegistry.from_directory 能加载当前所有有效 Skill。
- [x] registry.get、registry.require 和 registry.exposed_tools 替代手动 skill_index。
- [x] 名称重复、Schema 错误、MCP tool 缺失时失败，并包含 code 和 Skill 名称。
- [x] expose_to_model=false 的 follow-up 可被 Runtime 查找，但不出现在模型 Schema。
- [x] 迁移前后 Skill 名称集合、公开 Tool 名称和风险等级一致。

### 13.2 Run Loop 收敛

- [x] Turn 具备显式 `TurnPhase` 和 `StopReason`，并保留 `status/error` 兼容字段。
- [x] 无 Tool Call 时产生 final_answer 和 done(completed)。
- [x] Doom Loop 达到阈值后停止继续调用，并产生 doom_loop_detected。
- [x] 达到 max_steps 后产生用户可读最终答复，不出现只有 error 没有答复的路径。
- [ ] doom_loop、不可重试 Tool 错误和 max_steps 不互相覆盖，最终 `stop_reason` 保留最具体的终止原因。
- [ ] 同一 Tool 的等价默认参数和相同 Observation 达到阈值后，不再发起下一次 LLM 调用。
- [ ] doom、Tool 错误、超时和 max_steps 都经过同一个 Finalizer，终态事件只产生一次。
- [x] final_answer 不作为公开 Tool Schema。
- [x] LLM、Tool、审批、Context 和 Turn 超时均产生结构化停止原因和终态。
- [x] Business 已提交但 LLM 收尾失败时仍返回结构化成功答复。

### 13.3 流式输出

- [ ] LLM 文本增量可以通过 Redis Stream/SSE 逐步到达客户端。
- [x] Tool Call 参数尚未收完整时只产生增量事件，不提前执行。
- [x] Tool 执行前立即产生 tool_started。
- [x] Tool 完成后产生对应 tool_finished，包含 tool_call_id、耗时和结果/错误。
- [x] 最终答复使用 final_answer_delta，并最终产生一次完整 final_answer。
- [x] 长时间无下游事件时持续产生 heartbeat 或明确 waiting 状态。
- [x] after_seq 重连不重复执行 Turn，事件序号连续可解释。
- [x] 事件流等待超时不会静默断开，必须得到 stream_timeout 或 Turn 终态。

### 13.4 并行 Skill

- [x] 两个 parallel_safe 只读 Skill 可以并发执行。
- [x] 并发测试证明总耗时接近最长单个 Tool 耗时，而不是所有 Tool 耗时之和。
- [x] 单 Turn 并发数不超过 max_parallel_skills。
- [x] Tool Result 按原始 Tool Call 顺序写入，且每个 tool_call_id 唯一对应。
- [x] 一个只读 Tool 失败时，其他独立 Tool 的结果仍被记录并返回。
- [x] 未声明 parallel_safe 的 Skill 默认串行。
- [ ] `execution` 缺失、operation 级覆盖、`depends_on` 和 `max_concurrency` 的 Registry 校验有 focused tests。
- [ ] 只有显式 `parallel_safe` 的只读 operation 能进入并行队列；mixed、写操作和不明风险默认串行或启动失败。
- [x] 写操作、HITL follow-up 和同一资源更新不会并行提交。
- [x] Turn 并发限制与 Skill 并发限制分别有指标和配置。

### 13.5 错误处理与恢复

- [x] 定义统一错误对象，至少包含 `code`、`message`、`phase`、`tool_name`、`retryable` 和 `attempt`。
- [x] 错误分类至少覆盖瞬时错误、永久错误、模型错误和资源错误，并由分类结果决定恢复策略。
- [x] LLM 尚未产生流式输出、且错误属于瞬时错误时，使用有界异步指数退避和抖动重试。
- [x] LLM 已开始输出后断流默认不重试当前流，避免客户端收到重复增量；重试或终止原因必须可观测。
- [x] MCP 只读调用允许有限重试；写操作只有在幂等键和业务契约明确支持时才允许重试。
- [x] 参数缺失、未知 Tool、认证失败、审批冲突和业务不可重试错误不能盲目重试，并返回带上下文的结构化错误。
- [ ] 可恢复 Tool 错误进入 Observation 供模型调整；Runtime 崩溃、资源耗尽和终态错误必须进入 TurnFinalizer。
- [ ] 不可重试 Tool 错误不会被重复喂回模型直到 `max_steps`，除非存在 Registry 声明的安全 fallback。
- [x] `timeout`/`cancelled` 可作为过程事件发布，`done` 是唯一终态事件标记，避免终态事件被重复去重。
- [ ] fallback 只能来自 Skill/Registry 声明的安全替代关系，不能由模型自由改用其他写操作。
- [x] 重试耗尽、资源错误和关键路径持续失败具备明确的用户答复、运行告警或人工升级策略。
- [ ] 错误路径均有 Redis 状态、Trace、事件和最终答复，并覆盖重试、断流、MCP、审批、Context 和 Worker 异常测试。

### 13.6 真实链路

- [ ] 真实 Agent /api/v2/chat 收到 meta → started → action/progress → final_answer → done。
- [ ] 真实 MCP 查询收到 tool_started → tool_finished → observation。
- [ ] 真实 HITL 收到 approval_required → approval_result → operation_committed。
- [ ] 断开 SSE 后通过 after_seq 重连能补齐事件。
- [ ] Worker 重启或消息回收后不会重复执行已完成 Turn。
- [ ] 失败、取消、审批过期 Turn 都有 Redis 状态、Trace、事件和最终答复。

## 14. 建议测试文件和命令

建议新增：

~~~text
v2/tests/test_skill_registry.py
v2/tests/test_tool_batch_executor.py
v2/tests/test_react_loop_termination.py
v2/tests/test_agent_stream_events.py
v2/tests/test_turn_finalizer.py
v2/tests/test_skill_execution_policy.py
v2/tests/test_react_loop_no_progress.py
v2/tests/test_agent_run_loop_integration.py
~~~

基础验证：

~~~bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=agri_backend_v2 \
  agri_backend_v2/.venv/bin/pytest -q \
  agri_backend_v2/tests/test_skill_registry.py \
  agri_backend_v2/tests/test_tool_batch_executor.py \
  agri_backend_v2/tests/test_react_loop_termination.py \
  agri_backend_v2/tests/test_agent_stream_events.py \
  agri_backend_v2/tests/test_turn_finalizer.py
~~~

代码质量和结构验证：

~~~bash
ruff check agri_backend_v2/agent agri_backend_v2/tests
ruff format --check agri_backend_v2/agent agri_backend_v2/tests
bash scripts/check-complexity-budget.sh
~~~

真实服务验收至少需要：

~~~bash
BUSINESS_TEST_CLEANUP=0 BUSINESS_MAX_TIME=30 \
  agri_backend_v2/business/scripts/test_rest_api.sh

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=agri_backend_v2 \
  agri_backend_v2/.venv/bin/python agri_backend_v2/scripts/test_hitl_e2e.py
~~~

并行能力必须使用真实延迟 Skill 或可控测试替身，记录 parallel_batch_size、parallel_inflight_max、each_tool_duration_ms、batch_duration_ms、tool_failure_count 和 event_sequence。没有这些证据，只能说明代码存在并行分支，不能说明运行时真正并行。

## 15. 迁移顺序和风险

### 阶段一：命名和 Registry

- 新建 SkillRegistry；
- 由 react.py 使用 Registry 生成 Schema 和查找 Skill；
- 保留 skill_loader.load_all 兼容入口；
- 增加名称重复和 Schema 校验；
- 对比迁移前后的 Skill/Tool 名称集合。

### 阶段二：终态和流式事件

- 先修 final_answer 契约；
- 接通最终答复 delta；
- 立即发送 Tool Started；
- 增加 heartbeat 和 stream timeout；
- 统一 Finalizer。

风险：前端可能同时消费完整 final_answer 和 delta，必须保证同一答复不会重复拼接，且只保存一次完整消息。

### 阶段三：只读 Tool Batch 并行

- 增加 execution.mode；
- 默认全部 Skill 按 serial；
- 只把经过验证的只读 Skill 标记为 parallel_safe；
- 补齐 operation 级 execution/completion 投影和 Registry 启动校验；
- 先支持同一 assistant response，不修改 Plan 语义；
- 增加并发和失败隔离测试。

风险：并行只读请求可能依赖同一会话快照或外部服务限流，需要在 Registry 中明确依赖和并发上限。

### 阶段四：拆分 react.py

- 先抽 TurnFinalizer；
- 再抽 ToolBatchExecutor；
- 再抽 ReActLoop；
- 最后让 worker.py 只依赖 TurnRunner；
- 每一步保持旧 run_turn 适配入口。

风险：HITL follow-up、Plan 执行和普通 Tool 执行共享执行逻辑，拆分时必须保留同一套审批、Trace 和事件行为。

### 阶段五：无进展和错误终止收口

- 抽取稳定参数和 Observation 指纹计算；
- 将重复检测从“发警告”升级为 `FinalizationRequest`；
- 普通 Tool 错误按 retryable/category 分流，不允许不可重试错误循环消耗步数；
- 让 doom、错误、超时、取消和 max_steps 共用 Finalizer；
- 增加“不会退化成 max_steps”的回归测试和真实 MCP/SSE 证据。

风险：Observation 中包含分页、时间或请求标识等易变字段时，指纹不稳定会放行真正的死循环；指纹实现必须按 Skill 结果契约排除非业务字段，并保留原始结果用于 Trace。

## 16. 完成判定

只有同时满足以下条件，才能标记为 implemented：

1. Registry、Run Loop、Tool Batch、Progress Publisher 和 Finalizer 的职责在代码中可定位；
2. 同一 assistant response 的只读并行 Tool Call 有真实运行时和测试证据；
3. LLM、Tool、最终答复和 heartbeat 的事件可以通过 Redis Stream/SSE 观察和重连；
4. max_steps、doom、超时、取消、审批和异常都有用户可读终态；
5. Business 已提交与最终答复生成失败可以区分；
6. Runtime、Trace、Redis 状态、聊天持久化和前端事件没有互相矛盾的终态；
7. parallel_safe 只由显式 YAML 能力声明授予，operation 覆盖和默认串行规则有运行时证据；
8. 现有并发 Harness 和 HITL 设计的边界仍然成立；
9. 完成 focused tests、lint、复杂度检查和真实 Agent/MCP/SSE 验收。
