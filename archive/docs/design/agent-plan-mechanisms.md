---
last_updated: 2026-07-29
status: draft
---

# Agent Plan/Task 管理机制：两套设计记录

本文档**中立记录** farm-manager 后端当前在代码层面并存的两套"多步任务/计划管理"设计。不做推荐、不做对比矩阵，仅描述事实与契约。

## 概览

| 设计 | 物理位置 | 数据载体 | 当前状态 |
|---|---|---|---|
| 设计 A：DAG Plan IR（task_graph） | `backend/app/agent/task_graph/` | Pydantic 内存对象 | **未接入主链路**，零外部调用者 |
| 设计 B：表存储 | `backend/app/agent/pending_plan_*` + `backend/app/context/task_state.py` + `backend/app/application/chat/task_state_updater.py` | MySQL 3 张表 | pending_plans 活跃；task_states 半活跃 |

两套都在试图解决"用户给出写入/规划类意图后，Agent 如何分步执行 + 等待确认 + 跨轮承接"。

---

## 设计 A：task_graph（DAG Plan IR）

### 设计意图

把 Agent 多步任务抽象成可编译、可调度、可追溯的 DAG。参考 LangGraph / workflow engine 模式：用 IR（中间表示）解耦"语义意图"与"运行时执行"，便于静态校验、可视化、跨轮恢复。

核心抽象三层：
- **Plan IR**：人类/LLM 易写的语义层
- **TaskGraph**：编译后的 DAG（节点 + 依赖）
- **ExecutionState**：运行时状态机

### 模块结构

```
backend/app/agent/task_graph/
├── models.py                   # 320 行 — 全部数据契约
├── plan_ir.py                  # 141 行 — IR 创建 + 静态校验
├── compiler.py                 # 235 行 — IR → TaskGraph 编译器
├── router.py                   # 87  行 — Phase 1 任务类型路由
├── slot_extractor.py           # 161 行 — 自然语言 → PlanningSlotSet
├── evaluation.py               # 113 行 — 离线评测报告聚合
├── planning_context_builder.py # 41  行
├── raw_context_builder.py      # 28  行
├── capabilities/catalog.py     # 175 行 — 12 个预定义能力
├── runtime/state.py            # 106 行 — ExecutionState 状态机
├── runtime/scheduler.py        # 85  行 — DAG 调度
└── tasks/planting_plan/        # planting_plan 内部规划实现，未接入主链路外部调用

合计: 11 文件，1580 行
```

### 数据契约（models.py 核心 model）

#### 语义层

| Model | 关键字段 | 用途 |
|---|---|---|
| `FactSource` | `kind: user_input/tool_result/memory/rag/derived/system`, `ref`, `confidence` | 标记每个事实的来源（设计 A 独有概念） |
| `PlanningSlot` | `name`, `value`, `source: FactSource`, `normalized_unit` | 单个槽位 |
| `PlanningSlotSet` | `task_type`, `slots: dict[name, PlanningSlot]`, `missing_required_slots: list[str]` | 一轮槽位快照 |
| `RawContext` | `request_id`, `memory_refs`, `history_refs`, `rag_refs`, `db_refs`, `tool_cache_refs`, `runtime_refs` | 输入侧原始引用集合 |
| `PlanningContext` | `task_type`, `slots`, `facts`, `constraints`, `risk_policy`, `recent_task_refs` | 给 Planner 的完整上下文 |

#### Plan IR 层

```python
class PlanIRStep:
    step_id: str
    op: PlanIROp            # query|calculate|synthesize|branch|parallel|approval|wait|merge
    capability: str | None  # 引用 catalog 中的 CapabilityDefinition
    args: dict[str, Any]
    needs: list[str]        # 依赖的其他 step_id
    when: str | None        # 条件表达式
    optional: bool
    side_effect: SideEffect # none | pending_only | write（write 被禁止）

class PlanIR:
    ir_id: str
    task_type: TaskType
    intent: str
    planner_version: str
    context_hash: str       # 用于跨轮续接
    steps: list[PlanIRStep]
    response_contract: str
```

#### 编译后层

```python
class NodeContract:
    input_types: list[str]          # 类型契约（如 ["PlanningContext", "PlantingLayout"]）
    output_type: str                # 如 "PlantingPlanResponse"
    required_slots: list[str]
    side_effect: SideEffect
    failure_policy: FailurePolicy   # repair|ask_user|skip|hard_fail

class TaskGraphNode:
    node_id: str
    label: str
    source_ir_step_id: str | None
    invocation: OperatorInvocation  # CAPABILITY/IF/FOR/MAP/PARALLEL/WAIT/APPROVAL/MERGE
    contract: NodeContract
    depends_on: list[str]
    optional: bool

class TaskGraph:
    graph_id, source_ir_id, task_type, planner_version, context_hash
    nodes: list[TaskGraphNode]
    response_contract: str
```

#### 运行时层

```python
class ExecutionState:
    execution_id, graph_id
    status: created|running|paused|waiting_user|cancelled|completed|failed
    current_node_id, checkpoint_id
    completed_node_ids, failed_node_ids, dead_node_ids, skipped_node_ids
    retry_counts: dict[node_id, int]
    visited_node_ids
    pause_reason: str | None        # 仅 paused 时非空
    waiting_for: slot|confirmation|external_result | None  # 仅 waiting_user 时非空
    timeout_at, last_error_code

class NodeResult:
    node_id, status: success|skipped|needs_user|failed
    output_type, output: dict
    facts: dict[str, PlanningSlot]
    error_code
```

**model_validator 强约束**（ExecutionState）：
- `waiting_user` 状态必须携带 `waiting_for`
- `paused` 状态必须携带 `pause_reason`
- 非 `waiting_user`/`paused` 不能携带对应字段

#### 评测层（设计 A 独有）

```python
class EvaluationReport:
    slot_score: float                    # 槽位抽取准确度
    plan_ir_valid: bool                  # IR 静态校验是否通过
    graph_compile_success: bool          # 编译是否成功
    contract_pass_rate: float            # 契约匹配率
    capability_success_rate: float       # capability 执行成功率
    repair_count, retry_count            # 重写/重试次数
    hallucination_count                  # 幻觉计数
    latency_ms, token_count
    capability_metrics: dict[str, dict]  # 分 capability 的明细
```

支持按 `planner_version / task_type / capability / request_id` 4 个维度聚合（`aggregate_reports`）。

### Capability Catalog（capabilities/catalog.py）

预定义 12 个 Capability，每个都有严格契约：

| Capability | 输入 | 输出 | side_effect | failure_policy | adapter_hint |
|---|---|---|---|---|---|
| `QueryFarmStatus` | PlanningContext | FarmStatus | none | ask_user | get_farm_status |
| `QueryActiveCycles` | FarmStatus | ActiveCycleList | none | repair | manage_crop_cycle.query_cycles |
| `QueryPlantingUnits` | FarmStatus | PlantingUnitList | none | ask_user | manage_planting_units.query_units |
| `QueryCropTemplate` | PlanningSlotSet (crop) | CropTemplate | none | ask_user | manage_crop_templates.query_templates |
| `QueryWeatherForecast` | PlanningSlotSet (location) | WeatherForecast | none | skip | weather_adapter |
| `CalculatePlantingLayout` | PlanningSlotSet+CropTemplate | PlantingLayout | none | repair | deterministic_calculator |
| `CalculateArithmetic` | PlanningSlotSet | ArithmeticResult | none | repair | calculate_arithmetic |
| `SynthesizePlantingPlan` | PlanningContext+PlantingLayout | PlantingPlanResponse | none | hard_fail | response_synthesizer |
| `SynthesizeRequiredSlotQuestions` | PlanningContext | PlantingPlanResponse | none | ask_user | response_synthesizer |
| `ProposeCreateCyclePlan` | PlantingPlanResponse | PendingCyclePlan | **pending_only** | ask_user | pending_plan |
| `ProposeWorkOrderPlan` | PlanningContext | PendingWorkOrderPlan | **pending_only** | ask_user | pending_plan |
| `AnalyzeCost` | PlanningContext+PlantingLayout | CostAnalysis | none | skip | cost_capability |

`adapter_hint` 指向现有的 skill 名（如 `manage_crop_cycle.query_cycles`），但**没有实际绑定代码**——只是字符串提示。

### 静态校验规则（compiler.py，4 层）

`compile_plan_ir()` 依次执行：

1. **`validate_plan_ir`**（plan_ir.py）
   - `empty_plan`：至少 1 个 step
   - `missing_step_id` / `duplicate_step_id`
   - `unknown_op`：op 必须在 8 种 ALLOWED_OPS 内
   - `unknown_dependency`：needs 引用的 step_id 必须存在
   - `unsafe_write`：禁止 `side_effect="write"`，必须改为 `pending_only`

2. **`_validate_capabilities`**
   - `missing_capability`：CAPABILITY 类 op 必须有 capability 字段
   - `unknown_capability`：capability 必须在 catalog 内
   - `write_requires_approval`：pending_only capability 必须通过 approval op
   - `pending_capability_requires_pending_only`：声明一致性强校验

3. **`_validate_dag`**
   - `cyclic_graph`：DFS 检测环

4. **`_validate_contract_inputs`**
   - `missing_input_contract`：每个 capability 的 `input_types` 必须能从依赖节点的 output_type + 默认 `PlanningContext`/`PlanningSlotSet` 中找到

### Slot Extractor（slot_extractor.py）

目前只实现了 `extract_planting_plan_slots`，针对 planting_plan 任务：

- `_CROPS`: 番茄/黄瓜/西瓜/水稻/玉米/辣椒/茄子/草莓/小麦/大豆
- `_SEASONS`: 春夏秋冬（口语 + 规范化）
- `_KNOWN_LOCATIONS`: 太仓/苏州/徐州/睢宁/上海
- `_AREA_RE`: 匹配"X亩"，支持中英文数字（"三十"→30、"100"→100、"一百二十"→120）
- 自动 derived：`unit_count = total_area_mu / unit_area_mu`（标记 `kind=derived`, `ref="formula: ..."`）

输出 `PlanningSlotSet`，`missing_required_slots` 自动计算（默认检查 crop/season/total_area_mu 是否齐全）。

### ExecutionState 状态机（runtime/state.py）

```
                 ┌──────────────┐
                 │   created    │
                 └──────┬───────┘
                        │ start_execution
                        ▼
                 ┌──────────────┐
        ┌────────│   running    │────────┐
        │        └──────┬───────┘        │
        │ fail          │                │ pause_execution
        │               │ wait_for_user  │
        │               ▼                ▼
        │        ┌──────────────┐  ┌──────────────┐
        │        │ waiting_user │  │   paused     │
        │        └──────┬───────┘  └──────┬───────┘
        │               │ resume_execution│ resume_execution
        │               └────────┬───────┘
        │                        │
        │               mark_completed │
        │                        ▼
        │                ┌──────────────┐
        └───────────────▶│  completed   │
                         └──────────────┘

  任何非终态 ──cancel_execution──▶ cancelled
  running/waiting_user/paused ──fail_execution──▶ failed
```

转换严格校验前置条件（如 `paused` 只能从 `running` 进入；`completed` 只能从 `running` 进入）。

### Scheduler 算法（runtime/scheduler.py）

`next_runnable_nodes(graph, state)`：
1. 若 state.status 不在 `{created, running}` → 返回空
2. 收集所有 terminal 节点（completed + failed + skipped + dead）
3. 找依赖全部满足的节点（依赖在 completed 或 可选依赖在 skipped）
4. 过滤掉"依赖里有 ready 节点"的（避免一轮跑多个有依赖关系的）

`blocked_by_terminal_dependency(graph, state)`：找出因 failed/dead/non-optional-skipped 依赖而被阻塞的节点（用于死锁检测）。

### Router 实际支持范围（router.py）

虽然 TaskType 有 7 种，`route_task_type` 实际只路由到 3 种：

```python
def route_task_type(user_input: str) -> RouteDecision:
    # 1. 优先识别 retry_or_resume（命中"重试/再试/继续/恢复/上次/失败"）
    # 2. 其次识别 planting_plan（需 task_word + crop + season_or_time + area_or_plot 全命中，
    #    或 task_word + "茬口"）
    # 3. 默认 legacy_skill_fallback
```

匹配信号：
- `task_word`: 规划/计划/方案/茬口/安排
- `crop`: 草莓/番茄/西红柿/水稻/玉米/小麦/黄瓜/蓝莓
- `season_or_time`: 春夏秋冬 + 本月/下月/今年/明年
- `area_or_plot`: 数字+亩 / 地块/每块/块地

### 设计上预期的调用链路

```
user_input
  → router.route_task_type              # 识别 TaskType
  → raw_context_builder                 # 收集 db/memory/history/tool_cache refs
  → slot_extractor                      # 抽取 PlanningSlotSet（仅 planting_plan 实现）
  → planning_context_builder            # 组装 PlanningContext
  → create_plan_ir + validate_plan_ir   # 生成 IR + 第 1 层校验
  → compile_plan_ir                     # 第 2-4 层校验，输出 TaskGraph
  → create_execution_state              # 初始化运行时状态
  → scheduler.next_runnable_nodes       # DAG 调度
  → executor 执行节点（未实现）
  → NodeResult → ExecutionState 更新
  → EvaluationReport 落库（未实现）
```

### 当前状态：未接入主链路

```
$ grep -rn "from app.agent.task_graph" backend/app/ | wc -l
0
```

整个 `task_graph/` 目录**没有主链路外部调用者**：
- 12 个 capability 的 `adapter_hint` 只是字符串提示，未实际绑定 skill
- `tasks/planting_plan/` 已存在内部规划实现，包括 task planner、graph planner、execution planner、rules 和 response 生成
- 没有代码把 chat 流量导入 task_graph router

---

## 设计 B：表存储（MySQL 三张表）

### 设计意图

用关系表固化"多步写入确认"和"跨轮任务状态"。不追求 DAG 抽象，每张表对应一个明确职责，靠 SQL 字段和状态机约束保证一致性。当前运行时还包含 `runtime/planning/PlanDraft` 兼容规划层，并复用 `skills/registry` 作为 capability/operation 事实源。核心分摊：
- **短期**（pending_plan）：TTL 秒级，等用户确认就消费掉
- **长期**（task_state）：TTL 24h，跨多轮 hold 任务上下文
- **兼容规划合同**（PlanDraft）：把 router 决策投影为当前 runtime 可消费的轻量计划
- **能力注册表**（skills/registry）：保存 CapabilityDefinition、OperationDefinition、alias 和 YAML loader，后续规划层应复用它，不新增平行 registry

### B1. `agent_pending_plans` + `agent_pending_plan_steps`

**用途**：用户给出写入意图后，先把计划落库（status=pending），等用户确认后再逐 step 执行。TTL 过期自动失效。

当前 pending plan 创建保留多来源 fallback，迁移期不能一次性删除：

- `plan_draft`
- `crop_cycle_template_preflight`
- `tool_calls`
- `router_decision`

#### DDL 字段（`agent_pending_plans`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `plan_id` | varchar(64), unique | uuid hex |
| `farm_id` | int, FK farms | |
| `session_id` | varchar(64) | |
| `status` | varchar(32) | pending / running / completed / cancelled / expired / failed |
| `current_step_index` | int | 下一个待执行 step |
| `raw_user_input` | text | 触发该计划的原始用户消息 |
| `router_decision` | json | 当时的路由决策快照 |
| `router_decision_json` | json | 同上（兼容字段） |
| `expires_at` | datetime | TTL 失效时间 |
| `created_at` / `updated_at` | datetime | |

#### DDL 字段（`agent_pending_plan_steps`）

| 字段 | 类型 | 说明 |
|---|---|---|
| `plan_id` | varchar(64), FK + cascade | |
| `step_id` | varchar(64) | |
| `step_index` | int | 顺序 |
| `tool_name` / `skill_name` | varchar(100) | 调用的 skill |
| `params` / `params_json` | json | 该步骤参数（双写兼容） |
| `depends_on` | json | 同计划内依赖 |
| `confirmation_state` | varchar(32) | pending / confirmed / rejected |
| `execution_status` | varchar(32) | pending / running / executed / failed |
| `status` | varchar(20) | 统一状态字段：pending / executed / failed / cancelled / expired |
| `requires_confirmation` | tinyint(1) | 默认 1 |
| `confirmation_text` | text | |
| `result_payload` / `result_json` | json | 执行结果（双写兼容） |
| `error_payload` / `error_message` | text | 错误信息（双写兼容） |

> 注：多套字段（`status` vs `confirmation_state` vs `execution_status`，`params` vs `params_json`）是历史演进遗留，目前都双写。

#### 状态机

```
plan:    pending ──用户确认──▶ running ──全部 step executed──▶ completed
                ├──创建新 plan──▶ cancelled      ├──step failed──▶ failed
                └──TTL 到期──▶ expired            └──TTL 到期──▶ expired

step:    pending ──mark_step_executed──▶ executed
                ├──mark_step_failed──▶ failed
                ├──plan cancel──▶ cancelled
                └──plan expire──▶ expired
```

#### Service 方法（pending_plan_service.py）

| 方法 | 行为 |
|---|---|
| `create_pending_plan()` | 创建新 plan + steps；**同时 cancel_active_plan()**（同 session 互斥） |
| `get_active_plan()` | 取同 session 最近 active plan；若过期则同步标记 expired 并返回 None |
| `cancel_active_plan()` | 把所有同 session active plan 置 cancelled |
| `mark_step_executed(plan_id, step_index, result)` | 标记 step 为 executed；若无 pending step 则 plan→completed，否则 current_step_index 前移 |
| `mark_step_failed(plan_id, step_index, error_message)` | 标记 step 为 failed；plan→failed |
| `expire_stale_plans(now)` | 全局清理过期 plan |

#### 写入触发点（trace 实测）

`turn 175 "ok"` 走的就是这条链：
1. router 识别 write 意图（创建茬口）
2. 调 `create_pending_plan()` 落 2 个 step（确认模板 / 创建茬口）
3. trace 节点 64 `reflection_check.pre_write_plan` 校验 `pending_plan_consistency`
4. trace 节点 65 `skill_call.pending_plan` 返回 pending_plan
5. 用户下一轮"确认" → `reflection_check.pre_execution` 再校验 → 逐 step `skill_call.manage_crop_templates` / `manage_crop_cycle`

**当前状态：活跃**。

### B2. `agent_task_states`

**用途**：记录一个 session 内"进行中"的任务上下文（goal / entities / missing_information / next_action），让下一轮 Agent 能承接。区别于 pending_plan（一次性、TTL 短），task_state 是长生命周期的任务实体。

#### DDL 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | varchar(64), unique | uuid hex |
| `farm_id` | int, FK farms | |
| `user_id` | varchar(64) | |
| `session_id` | varchar(64) | |
| `task_type` | varchar(64) | planting_plan / crop_cycle_setup / ... |
| `goal` | text | 任务目标（user 原话压缩） |
| `entities_json` | json | 已知实体（地块/作物/季节...） |
| `observations_json` | json | 已观察事实 |
| `missing_information_json` | json | 还缺什么 |
| `next_action` | text | 下一步建议 |
| `status` | varchar(20) | active / waiting_user / completed / cancelled |
| `expires_at` | datetime | 默认 24h 后 |
| 索引 `(farm_id, user_id, session_id, status, updated_at)` | | 用于快速找 active task |

#### 状态机（TaskStateStatus）

```
                upsert (无 active)
                       │
                       ▼
              ┌─────────────────┐
              │     active      │◀──── _update_existing_task (无 missing)
              └────────┬────────┘
                       │ 有 missing_information
                       ▼
              ┌─────────────────┐
       ┌──────│  waiting_user   │──────┐
       │      └─────────────────┘      │
       │ user_cancel_intent            │ assistant_completion_signal
       │                               │ 或 pending_plan_completed
       ▼                               ▼
  ┌──────────┐                   ┌────────────┐
  │ cancelled│                   │ completed  │
  └──────────┘                   └────────────┘

  过期靠 expires_at 过滤（没有 expired status）
```

注意：状态枚举里**没有 `expired`**，过期任务靠查询时 `expires_at > now` 过滤。

#### Store 方法（AgentTaskStateStore）

| 方法 | 行为 |
|---|---|
| `upsert_active_task()` | 单会话单 active task：找现有 → 更新；找不到 → 创建。写入自动延展 `expires_at`（默认 +24h） |
| `get_active_task()` | 同 farm/user/session 最近未过期 active/waiting_user 任务 |
| `mark_completed(task_id)` | 状态 → completed |
| `mark_cancelled(task_id)` | 状态 → cancelled |

#### 写入触发点：task_state_updater.py 的启发式链

被 `application/chat/use_case.py:172` 和 `stream_finalization.py:221` 在 chat 收尾时调用。完整决策链：

```python
async def update_task_state_after_turn(db, turn):
    # 1. 前置过滤
    skipped = _skip_reason_before_decision(turn)
    #   → missing_identity_or_session / pending_write_confirmation
    #     / empty_turn / side_query

    # 2. 取现有 active task
    active = store.get_active_task(...)

    # 3. pending 决策完成检测（仅对 crop_cycle_setup）
    if turn.pending_decision_handled and active.task_type == "crop_cycle_setup":
        if _is_successful_pending_execution(turn.assistant_reply):  # 回复以"已执行"开头且不含失败词
            return mark_completed(active)

    # 4. 抽取 missing_information
    missing = _extract_missing_information(turn.assistant_reply)
        # 正则匹配: "还需要补充X"、"缺少X"、"请告诉我X"
    missing ||= _infer_missing_information_from_task_intent(turn.user_input)

    # 5. 已有 active task 的处理分支
    if active:
        if _is_cancel_turn(turn.user_input):     # "取消/算了/不要了"
            return mark_cancelled(active)
        if _is_side_query(turn.user_input):       # 查询类插入
            return skipped("side_query")
        if not missing and _is_completion_turn(turn):  # "好的/可以/完毕"
            return mark_completed(active)
        return _update_existing_task(active, missing)  # 合并 entities/observations

    # 6. 新建 task 的触发条件
    start_reason = _start_task_reason(turn, missing)
    #   → crop_cycle_setup_pending_plan
    #     / explicit_task_signal (含"帮我/请/麻烦")
    #     / natural_task_intent
    #   否则 → skipped("no_task_state_signal")

    # 7. 分类 + 抽实体 + 落库
    task_type = _classify_task_type(turn.user_input, turn.assistant_reply)
    entities = _extract_entities(turn.user_input)
    if task_type == "planting_plan":
        missing = _planting_plan_missing_from_entities(missing, entities)
    return _create_new_task_state(...)
```

**9 个语义判断函数**（启发式）：
- `_is_cancel_turn` / `_is_side_query` / `_is_completion_turn`
- `_is_successful_pending_execution`
- `_has_task_signal` / `_has_natural_task_intent`
- `_is_crop_cycle_setup_turn`
- `_extract_missing_information` / `_infer_missing_information_from_task_intent`
- `_extract_entities` / `_classify_task_type`

#### 读取触发点

`backend/app/context/selectors/task_state.py` 把 active task 格式化成 context_bundle 的 `active_task_state` block：
- `purpose`: "任务状态"
- `priority`: 90
- 输出 `_task_instruction(task)` 作为 system_prompt 一部分

注入时机：`context_build.context_bundle` 阶段（trace 节点 3 / 23 / 33 / 49 / 58 / 69 都能看到 `active_task_state` 在 selected_keys 里）。

#### 当前状态：路径完整但触发稀疏

- ✅ 读取链路通：context_bundle 会拉 active_task_state
- ⚠️ 写入稀疏：靠 chat 收尾启发式 + 9 个语义判断，多数 turn 落到 `no_task_state_signal` 兜底
- ❌ **`skill_router` 在 r1 阶段先于 `context_bundle`，看不到 task_state** — 这是 playground 多轮乱回答的根因之一

### 与设计 A 的桥接点

唯一桥接：`task_state_updater._is_crop_cycle_setup_turn()` 检测到 crop_cycle_setup 任务时，会把 pending_plan 纳入 task_state 触发条件（`_start_task_reason` 返回 `crop_cycle_setup_pending_plan`）。

但只对 `crop_cycle_setup` 这一种 task_type 做了桥接，其他 task_type 不联动。

---

## 两套设计的边界与重叠

### 都想解决

- 多步写入任务的拆分与确认
- 跨轮恢复（"重试"/"继续" 承接上文）
- 静态校验写操作安全性

### 各自独有

| 维度 | 设计 A (task_graph) | 设计 B (表存储) |
|---|---|---|
| 抽象层级 | 高（IR + Compiler + DAG） | 低（直接表 + service） |
| 状态载体 | Pydantic 内存对象 | MySQL 行 |
| 持久化 | 无（设计上未定） | 有 |
| 并行/分支 | 显式支持（`PARALLEL` / `IF` / `MERGE` operator） | 仅靠 `depends_on` 字段 |
| 可观测 | `EvaluationReport` 11 个指标 + capability 级聚合 | 靠 SQL + trace `skill_call` 节点 |
| 跨轮恢复 | 设计上靠 `context_hash` 续接 | pending_plan TTL；task_state 24h |
| 事实来源标注 | `FactSource.kind` 6 种（user/tool/memory/rag/derived/system） | 无 |
| 写操作保护 | 4 层静态校验强制 pending_only | 运行时 `reflection_check.pre_write_plan` + `pre_execution` |
| 接入现状 | 未接入 | pending_plan 活跃；task_states 半活跃 |

### 非重叠的职责

- **设计 A 独有**：Capability Catalog（12 个）、Slot Extractor（中英文数字解析）、`context_hash` 续接、`EvaluationReport` 评测层、`FactSource` 来源标记
- **设计 B 独有**：持久化（MySQL 行 + TTL 过期机制）、`task_states.missing_information_json` 启发式抽取、`pending_plan_steps.confirmation_state` 显式状态机、与 `reflection_check` 的运行时联动

### 枚举重叠（注意）

`TaskType` 字面值在两套里部分重叠，但分属不同 Python 枚举、无共享定义：

| TaskType | 设计 A (models.TaskType) | 设计 B (task_state_updater) |
|---|---|---|
| planting_plan | ✓ | ✓ |
| field_work_assignment | ✓ | ✗ |
| inventory_management | ✓ | ✗ |
| cost_analysis | ✓ | ✗ |
| pest_diagnosis | ✓ | ✗ |
| retry_or_resume | ✓ | ✗（靠 `_is_cancel_turn` 等启发式） |
| legacy_skill_fallback | ✓ | ✗ |
| crop_cycle_setup | ✗ | ✓（独有，桥接 pending_plan） |

---

## 当前事实清单（中性陈述）

1. `task_graph/` 共 11 个文件、1580 行，零外部调用者
2. `agent_pending_plans` 写入路径完整，trace 实测在用
3. `agent_task_states` 写入靠 chat 收尾启发式（9 个语义判断函数），读取在 `context_bundle` 阶段；`skill_router` 在 r1 先于 `context_bundle`，目前看不到该状态
4. 两套设计的 `TaskType` 字面有重叠，但分属不同 Python 枚举，没有共享定义
5. 唯一桥接点是 `task_state_updater._is_crop_cycle_setup_turn` 把 `crop_cycle_setup` 的 pending_plan 纳入 task_state 触发条件
6. playground session `playground-1785316095550-9w4ebd` 出现的 4 次乱回答，与"task_state 在 router r1 不可见"相关（详见 trace 链路分析）

本文档不包含方案推荐、对比矩阵或决策路径。这些留待后续独立文档。
