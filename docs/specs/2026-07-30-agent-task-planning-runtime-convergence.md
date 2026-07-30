# Agent Task Planning 与 Runtime 收敛方案

## 状态

- 状态：设计确认
- 日期：2026-07-30
- 目标读者：Agent 后端、Skill Router、Context Engine、Pending Plan、Trace/评测维护者
- 关联文档：
  - [Agent Plan/Task 管理机制：两套设计记录](../design/agent-plan-mechanisms.md)
  - [2026-07-29 Agent Task Graph 规划架构设计](./2026-07-29-agent-task-graph-planning-design.md)
  - [2026-07-24 Crop Cycle Setup Task Planning](./2026-07-24-crop-cycle-setup-task-planning.md)
  - [2026-07-10 Skill Capability Governance Design](./2026-07-10-skill-capability-governance-design.md)

## 结论

当前系统不应继续保留两套任务运行时。推荐采用收敛方案：

```text
TaskState 管“用户想完成什么”
PlanIR 管“应该怎么完成”
ExecutionPlan 管“运行时如何执行”
PendingPlan 管“允许执行什么”
Capability/Operation/Skill 管“真正执行什么”
```

也就是保留现有 `pending_plan + task_state` 作为持久化 Agent Runtime，吸收 `task_graph` 中已经沉淀的 Planning 能力，包括 `PlanningSlot`、`FactSource`、`PlanningContext`、`PlanIR`、静态校验、slot extractor、EvaluationReport。`task_graph/runtime/state.py` 和 `task_graph/runtime/scheduler.py` 不再作为长期方向。

这条路线可行，但必须渐进迁移。第一阶段优先解决 `task_state` 在早期 router 不可见的问题，并增加 Task Relevance Gate 防止历史任务污染当前输入；随后将 PlanIR 编译为 ExecutionPlan，再落到现有 PendingPlan，而不是先大规模移动目录或删除旧逻辑。

## 背景

系统目前存在两套相互重叠的多步任务机制：

- 设计 A：`backend/app/agent/task_graph/`
  - 优点是抽象清晰，具备 Plan IR、Capability Catalog、DAG compiler、slot extractor、事实来源标注和评测模型。
  - 问题是缺少主链路接入和持久化运行时。
- 设计 B：`pending_plan + task_state`
  - 优点是已经接入主链路，MySQL 持久化、用户确认、TTL、跨轮承接、reflection check 都在运行。
  - 问题是 planner 职责散落在 router、tool_pending、task_state_updater 和特定任务 preflight 中。

二者冲突的根因不是文件重复，而是职责边界没有切开：

- Router 在没有看到 `active_task_state` 时就做早期意图判断。
- 反过来，如果 `active_task_state` 无条件注入 router，也会把“天气怎么样？”这类旁路问题误判为继续旧任务。
- PendingPlan 既承担“待确认执行计划”，又承担部分“计划生成”职责。
- TaskState 保存了跨轮任务上下文，但多数写入靠 chat 收尾启发式，触发稀疏。
- TaskState 更新仍依赖 assistant reply 和正则，不应作为长期事实抽取机制。
- TaskType、状态机和能力定义分散，导致同一业务任务在多轮里不能稳定承接。

## 当前代码基线

本设计基于 2026-07-30 的代码状态：

- `task_graph` 没有外部主链路调用者，但内部已经存在 `tasks/planting_plan` 规划实现，不是纯占位目录。
- `backend/app/agent/runtime/planning/` 已存在 `PlanDraft`、`PlanStep`、`PlanValidationResult`，并已作为 pending plan 的兼容入口之一。
- `backend/app/skills/registry/` 已存在 `CapabilityDefinition`、`OperationDefinition`、alias 和 YAML loader。
- `tool_pending._pending_plan_tool_message()` 已按 `plan_draft`、`crop_cycle_template_preflight`、`tool_calls`、`router_decision` 多来源创建 pending plan。
- `TaskStateSelector` 已能输出 `active_task_state` context block，但该 block 进入 `context_bundle` 的时机晚于部分 router 决策。

因此，后续不应再新增平行的第三套 `agent/capabilities` 或 `agent/planner` 事实源。新增目录可以作为最终结构目标，但第一阶段必须优先复用现有 `runtime/planning` 与 `skills/registry`。

## 目标

1. 让 `task_state` 在 Intent Router 和 Planner 之前可见，解决“20亩”“继续”“确认按刚才的方案”这类跨轮短输入无法理解的问题。
2. 统一 TaskType 的事实源，避免 `task_graph.models.TaskType` 与 task_state 启发式字符串继续分裂。
3. 将 `task_graph` 收缩为 Planning Layer，保留 Plan IR、slot/fact/context、compiler/validator、evaluation，移除长期 runtime 定位。
4. 让 PendingPlan 成为所有写操作的唯一待确认执行载体。
5. 让写操作形成固定安全路径：`User Input -> TaskState Retrieval -> Relevance Gate -> PlanningContext -> PlanIR -> Validator -> ExecutionPlan -> PendingPlan -> User Confirm -> Executor -> Skill`。
6. 让现有 `PlanDraft` 成为兼容桥，而不是废弃重写。
7. 在 trace 中统一观察 `task_state.load`、`planner.generate`、`plan.validate`、`pending_plan.create`、`skill.execute`。
8. 将 TaskState 更新从 reply 正则解析逐步迁移到结构化 Turn Result。
9. 明确 Capability、Operation、Skill 三层关系，避免再次把 capability 和 tool name 混成一层。

## 非目标

1. 不一次性替换所有 Skill Router。
2. 不第一阶段删除 `tool_pending` 的多来源 fallback。
3. 不第一阶段实现完整 DAG workflow engine。
4. 不新增与 `backend/app/skills/registry/` 平行的 Capability Registry。
5. 不让 LLM 直接生成可执行数据库写入。
6. 不迁移历史 pending plan 表结构，除非已有字段无法表达 PlanIR 编译结果。

## 目标架构

```text
User Input
  -> Identity / Session
  -> TaskState Retrieval
  -> Task Relevance Gate
  -> Context Builder
  -> Intent Router
  -> Planning Layer
       -> Slot Extraction
       -> PlanningContext
       -> PlanIR
       -> Validator / Compiler
       -> ExecutionPlan
  -> PendingPlan
  -> User Confirmation
  -> PendingPlan Executor
  -> Capability
  -> Operation
  -> Skill
  -> Result Update
  -> TaskState Update
  -> Evaluation / Trace
```

分层职责如下：

| 层 | 职责 | 不负责 |
| --- | --- | --- |
| TaskState | 当前用户任务、目标、实体、缺失信息、跨轮恢复 | 生成执行步骤、调用 Skill |
| Task Relevance Gate | 判断当前输入是否应承接 active task | 改写用户意图、直接选择 Skill |
| PlanningContext | 把 user input、task_state、memory、RAG、DB refs 组织成 planner 可消费上下文 | 执行工具、写库 |
| PlanIR | 表达业务步骤、依赖、能力、风险和确认意图 | 保存运行状态 |
| Validator/Compiler | 静态校验、能力契约校验、写操作安全校验、编译为 ExecutionPlan | 持久化生命周期 |
| ExecutionPlan | 表达 runtime 可执行的 skill、operation、params、顺序和确认要求 | 保存 TTL、用户确认状态、执行结果 |
| PendingPlan | 持久化待确认步骤、TTL、执行进度、失败状态 | 规划业务流程 |
| Capability/Operation/Skill | 执行具体业务能力 | 决定跨轮任务目标 |

## 关键设计决策

### 1. B 是 Runtime，A 是 Planning

保留 B 的 MySQL 持久化、pending confirmation、TTL 和执行状态。A 中的 `ExecutionState` 与 `Scheduler` 只作为历史设计参考，不作为长期运行时。

原因：

- PendingPlan 已经接入主链路和用户确认。
- 写操作安全必须落在持久化状态上，不能只停留在内存 Pydantic 对象。
- 当前农业 Agent 的多数多步写入是顺序确认，不需要第一阶段引入完整 DAG runtime。

### 2. 优先修 Context 顺序，但必须经过 Task Relevance Gate

当前乱回答的高优先级原因是 router 早于 `active_task_state`。因此第一批改造应增加早期 task state 读取：

```text
User Input
  -> TaskState Retrieval
  -> Task Relevance Gate
  -> Intent Router
  -> Planner
  -> Skill Router
```

而不是：

```text
User Input
  -> Skill Router
  -> Context Bundle
```

早期读取可以先复用 `AgentTaskStateStore.get_active_task()`，并把结果作为 router/planner 的显式参数传入。后续再统一到 Context Engine。

但是 active task 不能无条件注入 router。必须先判断当前输入是否和当前任务相关，否则历史任务会污染旁路查询。

Task Relevance Gate 的输入：

```json
{
  "user_input": "天气怎么样？",
  "active_task": {
    "task_type": "planting_plan",
    "missing_information": ["total_area_mu"],
    "entities": {
      "crop": "西瓜",
      "season": "春季"
    }
  }
}
```

建议输出：

```json
{
  "score": 0.2,
  "decision": "do_not_inject",
  "reason": "side_query_weather"
}
```

高相关输入示例：

| 用户输入 | active task | score 建议 | 行为 |
| --- | --- | --- | --- |
| `20亩` | 缺面积的 `planting_plan` | 0.95 | 注入 task_state 并补槽 |
| `继续` | 任意 waiting_user/active task | 0.9 | 注入 task_state |
| `确认` | 有 pending confirmation | 0.95 | 优先处理 pending |
| `按刚才的方案创建` | 已完成方案但未落地 | 0.9 | 注入 task_state |
| `天气怎么样？` | `planting_plan` | 0.2 | 不注入，走独立查询 |
| `今天温度多少？` | `crop_cycle_setup` | 0.2 | 不注入，走天气/设置查询 |

第一阶段可以 rule-first：

- 短输入且 active task 有 missing slot，尝试槽位类型匹配。
- `继续`、`再试一下`、`确认`、`按刚才`、`就这样` 属于强承接信号。
- 明确查询天气、价格、设置、闲聊时属于旁路信号。
- pending confirmation 优先级高于普通 active task。

阈值建议：

- `score >= 0.75`：注入 active task 到 router/planner。
- `0.4 <= score < 0.75`：仅作为低优先级 context，不改变 router 主判断。
- `score < 0.4`：不注入 active task。

### 3. PlanIR 与 PendingPlanStep 之间增加 ExecutionPlan

`PlanIR -> PendingPlanStep` 直接转换跨度过大。PlanIR 面向 planner，PendingPlanStep 面向数据库状态，中间需要一个 runtime 合同：

```text
PlanIR
  -> Validator / Compiler
  -> ExecutionPlan
  -> PendingPlan
```

PlanIR 负责表达：

- 为什么做。
- 怎么拆。
- 业务依赖。
- 风险和确认意图。
- capability 层意图。

ExecutionPlan 负责表达：

- 调哪个 skill/tool。
- 调哪个 capability operation。
- 参数是什么。
- 执行顺序是什么。
- 哪些步骤需要确认。
- 哪些字段来自前置步骤结果。

PendingPlan 负责表达：

- plan/step 状态。
- TTL。
- 用户确认。
- 执行结果。
- 失败信息。

建议第一版 ExecutionPlan 模型：

```python
class ExecutionStep:
    step_id: str
    capability: str
    operation: str
    skill_name: str
    params: dict
    depends_on: list[str]
    requires_confirmation: bool
    side_effect: str


class ExecutionPlan:
    plan_id: str
    source_ir_id: str
    task_type: str
    steps: list[ExecutionStep]
    validation_version: str
```

`PendingPlanStep` 只从 `ExecutionStep` 投影出 DB 需要的字段，不再承载 planner 语义。

### 4. 复用现有 PlanDraft 作为桥接层

系统已经有 `PlanDraft`：

```text
backend/app/agent/runtime/planning/models.py
```

它的 `route_type`、`steps`、`missing_fields`、`validation` 已经能表达轻量单轮计划。后续可以建立两个 adapter：

```text
RouterDecision -> PlanDraft
PlanIR -> ExecutionPlan -> PendingPlanStep
```

迁移期允许 `PlanDraft` 和 `PlanIR` 并存，但必须明确：

- `PlanDraft` 是兼容路由合同，服务当前 runtime。
- `PlanIR` 是长期 planner 输出合同，表达业务计划。
- `ExecutionPlan` 是 runtime 执行合同，服务 capability/operation/skill 解析。
- PendingPlanStep 是数据库确认状态合同，服务写操作落库。

### 5. Capability Registry 复用现有 skills/registry，但保持三层语义

现有 `backend/app/skills/registry/loader.py` 已定义 `CapabilityDefinition` 和 `OperationDefinition`。后续应扩展该 registry 的 schema，而不是新增 `backend/app/agent/capabilities/` 作为并行事实源。

命名上要避免把 `Capability` 等同于 `Skill`。长期语义应保持三层：

```text
Capability
  -> Operation
  -> Skill Tool
```

示例：

```text
Capability: crop_cycle_management
Operation: create_cycle
Skill Tool: manage_crop_cycle
```

这样 planner 可以面向业务能力规划，runtime 可以面向 operation 做风险和权限判断，executor 最终再解析到具体 skill/tool。

需要补充的字段可以渐进加入：

- `input_schema`
- `output_schema`
- `side_effect`
- `requires_confirmation`
- `executor_ref`
- `planner_hints`
- `failure_policy`

### 6. TaskState 更新从 reply 正则迁移到结构化 Turn Result

当前 `task_state_updater` 在 chat 收尾阶段基于 `assistant_reply` 和正则推断任务状态。这能作为兼容兜底，但不应作为长期主路径。

长期应改为：

```text
Turn Result
  -> TaskState Extractor
  -> TaskState Update
```

其中 Turn Result 来自 router/planner/executor 的结构化输出，而不是最终回复文本：

```json
{
  "intent": "plan_crop_cycle",
  "task_type": "planting_plan",
  "entities": {
    "crop": "西瓜",
    "season": "春季",
    "total_area_mu": 20
  },
  "missing_slots": ["unit_area_mu"],
  "plan_result": {
    "plan_ir_id": "pir:xxxx",
    "validation_status": "blocked"
  },
  "execution_result": null
}
```

更新规则：

- Planner 已知的 `missing_slots` 直接写入 task_state，不再从回复中正则提取。
- Slot extractor 已知的 `entities` 直接合并 task_state。
- PendingPlan completed/failed/cancelled 直接驱动 task_state 状态迁移。
- assistant reply 正则只保留为 legacy fallback，并需要 trace 标记 `source="reply_regex"`。

### 7. Executor 接口提前稳定

PendingPlan Executor 是后续 trace、reflection、evaluation 的共同依赖，不能只作为黑盒执行器。建议第一版接口：

```python
class CapabilityExecutor:
    async def execute(
        self,
        *,
        capability: str,
        operation: str,
        skill_name: str,
        params: dict,
        context: dict,
    ) -> ExecutionResult:
        ...


class ExecutionResult:
    status: str
    output: dict | None
    facts: dict
    error: dict | None
    trace: dict
```

返回结果必须能支撑：

- pending step result 更新。
- TaskState entities/observations 更新。
- Reflection 节点级校验。
- Evaluation 按 capability/operation 聚合。
- Trace 脱敏输出。

### 8. PendingPlan 来源收敛，但保留 fallback

当前 pending plan 创建来源包括：

- `plan_draft`
- `crop_cycle_template_preflight`
- `tool_calls`
- `router_decision`

迁移目标是：

```text
PlanIR
  -> Validator
  -> ExecutionPlan
  -> PendingPlanStep
  -> store_pending_plan()
```

但在 PlanIR 覆盖率达标前，必须保留现有 fallback。删除顺序应由 trace 和评测数据驱动，而不是按目录清理驱动。

### 9. 写操作必须 fail-closed

所有数据库写操作必须满足：

```text
PlanIR side_effect=write
  -> Validator 改写或拒绝
  -> ExecutionPlan requires_confirmation=true
  -> PendingPlan side_effect=pending_only
  -> User Confirm
  -> Executor 执行 Skill
```

禁止路径：

```text
LLM -> tool_call -> database write
```

即使 LLM 直接产出 tool call，也必须被 `tool_pending` 或后续统一 executor 拦截并转为 pending confirmation。

## 迁移计划

### Phase 0：事实基线修正

目标：确保文档和代码事实一致。

任务：

- 更新 `agent-plan-mechanisms.md`，说明 `task_graph/tasks/planting_plan` 已存在内部实现，但没有主链路外部调用者。
- 标注 `runtime/planning/PlanDraft` 与 `skills/registry` 已存在，避免后续方案重复造结构。
- 补充当前 pending plan 多来源 fallback 清单。

验收：

- 文档不再描述 `task_graph/tasks/__init__.py` 为唯一占位。
- `rg "app.agent.task_graph" backend/app --glob '!backend/app/agent/task_graph/**'` 无主链路调用者。

### Phase 1：早期 TaskState Retrieval 与 Relevance Gate

目标：让 router/planner 在决策前有条件地看到当前任务，既支持跨轮承接，又避免历史任务污染旁路查询。

任务：

- 新增早期 task state loader，复用 `AgentTaskStateStore.get_active_task()`。
- 新增 Task Relevance Gate，输出 `score`、`decision`、`reason`。
- 只有相关性达到阈值时，才将 active task 作为显式参数传给 intent router 或 plan draft builder。
- 为短输入补槽增加测试，例如“20亩”“继续”“确认”“按刚才的方案创建”。
- 为旁路查询增加测试，例如 active task 存在时用户问“天气怎么样？”不能误承接。
- trace 增加 `task_state.load` 节点。
- trace 增加 `task_state.relevance` 节点。

验收：

- 当 active task 为 `planting_plan` 且缺少面积时，用户输入“20亩”不会进入无关查询或直接回复。
- 当 active task 为 `crop_cycle_setup` 且用户确认时，优先进入 pending confirmation/execution 逻辑。
- 当 active task 存在但用户提出独立天气/设置/闲聊问题时，不把该输入强行路由为旧任务补槽。

### Phase 2：PlanIR 到 ExecutionPlan/PendingPlan Adapter

目标：让 A 的 Planning 能力进入 B 的 Runtime。

第一条垂直切片优先选择 `crop_cycle_setup`，而不是 `planting_plan`。原因是 `crop_cycle_setup` 已有 pending、confirmation、skill 执行链路，适合验证 adapter 是否破坏现有写操作安全路径。

任务：

- 新增 `PlanIR -> ExecutionPlan` adapter。
- 新增 `ExecutionPlan -> PendingPlanStep` adapter。
- `crop_cycle_setup` 先覆盖 ensure template、create cycle、optional planting unit 三类步骤。
- 将 `side_effect=write` 的步骤编译为 `requires_confirmation=true`。
- 将 read/calculate/synthesize 步骤在第一阶段保守处理，不强行落库为待执行写步骤。
- 在 `tool_pending` 中增加 `source="plan_ir"` 分支，但保持现有 fallback。

验收：

- 创建茬口类请求可以由 PlanIR 通过 ExecutionPlan 创建 pending plan。
- validator 拒绝未知 capability、缺少必填参数、未确认写操作。
- 原有 pending plan 测试继续通过。
- trace 能看到 `planner.generate`、`plan.validate`、`execution_plan.compile`、`pending_plan.create`。

### Phase 3：TaskType、Registry、Trace 收敛

目标：收口共享定义和可观测性。

任务：

- 新增共享任务类型模块，建议位置为 `backend/app/agent/task_types.py` 或更通用的 `backend/app/shared/task_types.py`。
- 先提供兼容导出，不第一步大规模改 import。
- 覆盖现有字面值：`planting_plan`、`crop_cycle_setup`、`field_work_assignment`、`inventory_management`、`cost_analysis`、`pest_diagnosis`、`retry_or_resume`、`legacy_skill_fallback`。
- 为 task_state、task_graph、router 分类结果增加一致性测试。
- 在 `skills.yaml` 增加 planner 所需字段。
- 建立 `capability.operation -> legacy tool/skill` 解析器。
- 把 `task_graph/capabilities/catalog.py` 的能力定义迁移或映射到现有 registry。
- 保留旧 alias，确保 trace replay 和 pending action 不断。
- 统一 trace 节点命名，补齐 `task_state.relevance` 与 `execution_plan.compile`。

验收：

- 新增 TaskType 不再需要同时修改多个枚举。
- 现有 task_state 落库字面值保持向后兼容。
- PlanIR 中的 capability 可以解析到唯一 operation。
- 写风险和 confirmation 策略来自 registry，而不是散落在 router 规则中。

### Phase 4：TaskState 更新机制收敛

目标：从 reply 正则迁移到结构化 Turn Result。

任务：

- 定义 `TurnResult` 或等价结构。
- Planner 输出 `task_type`、`entities`、`missing_slots`。
- Executor 输出 `execution_result` 与 `facts`。
- `task_state_updater` 优先消费结构化 Turn Result。
- assistant reply 正则保留为 legacy fallback，并打 trace。

验收：

- 缺失信息不再依赖回复文案格式。
- pending plan 完成、失败、取消能稳定驱动 task_state 状态迁移。
- 旁路查询不会误完成 active task。

### Phase 5：Runtime 收敛与旧逻辑删除

目标：删除重复 runtime，不破坏生产链路。

任务：

- 删除或归档 `task_graph/runtime/state.py` 与 `scheduler.py`。
- 将 `TaskGraph` 相关模型从长期执行合同中移除，或标记为 legacy planning compile artifact。
- 收敛 `tool_pending` 的多来源 fallback，保留已被 trace 证明仍需要的兼容路径。
- 将 `crop_cycle_setup_planner` 这类特定 preflight 迁移到 planner/capability 规则中。

验收：

- 所有写操作仍经过 PendingPlan。
- 无外部调用依赖被删除模块。
- harness、pending plan、task state、router 相关测试通过。

## Trace 设计

统一 trace 节点建议：

```text
request.start
task_state.load
task_state.relevance
context.build
intent.route
planner.generate
plan.validate
execution_plan.compile
pending_plan.create
user.confirm
skill.execute
pending_plan.update
task_state.update
response.final
evaluation.record
```

每个节点至少包含：

- `request_id`
- `farm_id`
- `session_id`
- `task_id`
- `task_type`
- `planner_version`
- `capability_version`
- `operation`
- `source`
- `status`
- `error.code`

敏感字段必须脱敏，沿用现有 `_redact_payload` 风格。

## Evaluation 设计

保留 A 的 `EvaluationReport` 思路，但落到主链路指标：

- slot 抽取准确率。
- task_state 承接成功率。
- task_state relevance gate 准确率。
- PlanIR 静态校验通过率。
- ExecutionPlan 编译成功率。
- pending plan 创建成功率。
- 用户确认后执行成功率。
- capability/operation 成功率。
- repair/retry 次数。
- 无关回答率。
- 写操作越权拦截数。
- latency/token。

第一阶段不要求全部落库，可以先在 trace 和离线报告中聚合。

## 测试策略

必测用例：

- active planting task 缺面积，用户补“20亩”。
- active planting task 缺季节，用户补“秋季”。
- active task 存在，用户问“天气怎么样？”时不能污染旧任务。
- active task 存在，用户问“今天温度多少？”时应走独立天气查询。
- 用户说“继续”“再试一下”时能读取上次 task_state。
- 创建茬口仍进入 pending plan，而不是直接写库。
- `crop_cycle_setup` 通过 `PlanIR -> ExecutionPlan -> PendingPlan` 垂直链路创建待确认计划。
- 多步骤 pending plan 保持确认后顺序执行。
- PlanIR 中未知 capability 被 validator 拒绝。
- PlanIR 中写操作未进入 pending confirmation 被 validator 拒绝。
- ExecutionPlan 中 capability/operation/skill 不能解析时必须 fail-closed。
- task_state side query 不应错误完成当前任务。

建议命令：

```bash
poetry run pytest tests/agent tests/services/test_pending_plan_service.py -q
bash scripts/check-layer-deps.sh
bash scripts/check-complexity-budget.sh
```

## 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 一次性移动目录过多 | import 断裂，主链路回归难定位 | 先 adapter，后搬迁 |
| 新增 Capability Registry 平行事实源 | 能力定义再次分裂 | 复用 `skills/registry` |
| Capability 和 Skill 混成一层 | planner 与 executor 边界再次混乱 | 保持 Capability -> Operation -> Skill 三层 |
| active task 无条件注入 router | 旁路查询被误判为旧任务补槽 | 增加 Task Relevance Gate |
| PlanIR 直接落 PendingPlanStep | planner 语义污染 DB 执行状态 | 增加 ExecutionPlan 中间层 |
| TaskState 继续依赖回复正则 | 文案变化导致任务状态漂移 | 改为结构化 Turn Result 优先 |
| 过早删除 pending plan fallback | 现有写操作确认失败 | trace 覆盖率达标后逐项下线 |
| TaskType 统一影响历史数据 | 老 task_state 无法恢复 | 保持字符串兼容，先兼容导出 |
| PlanIR 覆盖读/写/合成过宽 | 第一阶段复杂度失控 | 只做一个垂直切片 |
| LLM planner 不稳定 | pending plan 错误创建 | rule-first、schema validate、fail-closed |

## 推荐实施顺序

推荐先做：

1. Phase 0：修正文档事实基线。
2. Phase 1：早期读取 TaskState，并增加 Task Relevance Gate。
3. Phase 2：以 `crop_cycle_setup` 做 `PlanIR -> ExecutionPlan -> PendingPlan` 最小切片。
4. Phase 3：收敛 TaskType、Registry、Trace。
5. Phase 4：将 TaskState 更新从 reply 正则迁移到结构化 Turn Result。
6. Phase 5：删除旧 runtime。

不推荐先做：

- 直接新增完整 `agent/planner/`、`agent/capabilities/` 目录。
- 直接删除 `task_graph/runtime`。
- 直接把所有 pending plan 创建改成 PlanIR。
- 直接把 PlanIR 投影到 PendingPlanStep，跳过 ExecutionPlan。
- 无条件把 active task 注入 router。
- 直接让 LLM 生成全量执行计划并落库。

## 最终判断

该收敛方案可行，且是当前 farm-manager Agent 走向稳定多轮业务任务的必要步骤。关键不是引入更复杂的 workflow engine，而是先把 Planning、Runtime、Memory、Execution 的边界切开，并把已有能力接到同一条安全路径上。

第一版成功标准很明确：当用户在多轮对话中补充缺失信息或确认执行时，系统能基于 `TaskState` 正确续接，并把所有写操作稳定收敛到 `PendingPlan`，不再让 router、LLM tool call 和 pending plan 各自生成一套任务语义。
