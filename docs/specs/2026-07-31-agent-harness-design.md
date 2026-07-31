# Agent Harness 设计：现状与目标

## 状态

- 状态：架构基线（现状 + 目标对照）
- 日期：2026-07-31
- 目标读者：Agent 后端、Skill Router、Pending Plan、Trace/评测、新加入成员
- 关联文档：
  - [Agent Plan/Task 管理机制：两套设计记录](../design/agent-plan-mechanisms.md)
  - [2026-07-30 Agent Task Planning 与 Runtime 收敛方案](./2026-07-30-agent-task-planning-runtime-convergence.md)
  - [2026-07-29 Agent Task Graph 规划架构设计](./2026-07-29-agent-task-graph-planning-design.md)
  - [Agent 开发规范](../agent/agent-development-standard.md)

## 目的

一份文档同时承载两个状态：

- **现状**：当前代码实际怎么跑（事实，给新人/调试用）
- **目标**：理想 harness 应该长什么样（方向，给架构决策用）

每个组件都先讲现状再讲目标，紧贴对比。推进路径用阶段划分，每阶段都标注可验证、可回滚。

---

## 一、执行链路：现状 vs 目标

### 1.1 现状链路（ReAct 单循环，无显式 Planner）

```text
HTTP /chat/stream
    │
    ▼
application/chat/stream_chat_events → stream_advisor
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ agent/runtime/loop.py: stream_agent_loop                      │
│ for _step in range(max_steps=15):                             │
│                                                               │
│   ┌────────────────────────────────────────────────────────┐ │
│   │ _llm_node                                               │ │
│   │  ① Router (规则,每轮跑)                                 │ │
│   │     → RouterDecision + PlanDraft                        │ │
│   │  ② Reflection: PRE_WRITE_PLAN                           │ │
│   │  ③ Context 组装 (task_state 在 r1 不可见 ⚠️)            │ │
│   │  ④ Prompt 渲染                                          │ │
│   │  ⑤ LLM 调用 (bind_tools)                                │ │
│   │  ⑥ Reflection: POST_TOOL_RESULT                         │ │
│   │  ── 无 tool_calls → return ──                           │ │
│   └────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          ▼                                    │
│   ┌────────────────────────────────────────────────────────┐ │
│   │ _parallel_tool_node                                     │ │
│   │  ⑦ Permission Decision (WRITE_SKILLS → pending)        │ │
│   │  ⑧ 写操作: pending_plan 落表 (status=pending)         │ │
│   │  ⑨ 只读: 并行 invoke skills                            │ │
│   │  ⑩ Reflection: PRE_EXECUTION                           │ │
│   └────────────────────────────────────────────────────────┘ │
│                          │                                    │
│                          └──→ 下一轮 _llm_node                │
└──────────────────────────────────────────────────────────────┘
                          │
                          ▼
task_state_updater (启发式) → save turn
```

### 1.2 目标链路（5 个显式 Stage）

```text
HTTP /chat/stream
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 1: Task Understanding                                  │
│   ─ TaskState 注入 (r1 可见,修复现状⚠️)                      │
│   ─ Router 风险分级 (规则,确定性)                            │
│   ─ Task Relevance Gate (防历史任务污染)                     │
│   ─ trace: router.r1, task_state.relevant                    │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 2: Planner (新增,显式阶段)                             │
│   ─ 规则 PlanDraft (稳定基线)                                │
│   ─ 可选 LLM PlannerOutput (probe 已验证 schema)             │
│   ─ Hybrid: 规则做骨架, LLM 做增强                           │
│   ─ 输出作为软提示注入 system prompt,不强制约束 ReAct        │
│   ─ trace: planner.draft (独立节点)                          │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 3: ReAct Loop (现有,加 plan 软提示)                    │
│   ─ Context 组装 (含 plan_hint)                              │
│   ─ Prompt 渲染 (system + plan_hint + tool schema)           │
│   ─ LLM bind_tools + Reasoning                               │
│   ─ Tool Executor (并行)                                     │
│   ─ Reflection: 5 触发点                                     │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 4: Write Gate (现有 PendingPlan,职责不变)              │
│   ─ 写操作 fail-closed                                       │
│   ─ HITL 确认回环                                            │
│   ─ reflection: PRE_EXECUTION 校验                           │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│ Stage 5: Finalize + Evaluation                               │
│   ─ task_state_updater (规则+LLM hybrid)                     │
│   ─ save turn to MySQL/Mongo                                 │
│   ─ evaluation hook: probe / replay / 回归门禁               │
└──────────────────────────────────────────────────────────────┘
```

### 1.3 关键差异表

| 维度 | 现状 | 目标 |
|---|---|---|
| Router r1 看见 task_state | ❌ | ✅ |
| 显式 Planner 阶段 | ❌ (嵌在 Router) | ✅ (Stage 2) |
| LLM PlannerOutput schema | ❌ | ✅ |
| `planner.draft` 独立 trace 节点 | ⚠️ 半 | ✅ |
| Task Relevance Gate | ❌ | ✅ |
| Plan 软提示注入 ReAct | ❌ | ✅ |
| Evaluation hook 集成 | ⚠️ 部分 | ✅ |

### 1.4 现状关键事实

- **没有「Planner 一次性拆解」这一步**。Router 嵌在每轮 LLM 调用前，只决定「这轮给 LLM 暴露哪些工具 + 风险等级」，不输出多步计划。
- **没有「Plan-and-Execute」分离**。LLM 每轮看 messages 自己决定下一步，这就是 ReAct。
- **Reflector 不是末尾一次**，是 5 个触发点散在循环各处的嵌入式检查。

---

## 二、核心组件：现状 vs 目标

### 2.1 SkillRouter

**位置**：`backend/app/agent/router/`

**现状职责**：

| 必须做 | 禁止做 |
|---|---|
| 风险分级（read / write_confirm / write_high） | 长期维护业务关键词词库 |
| 候选工具预算（向量召回 + 规则扩链） | 硬编码"财务/账务/茬口/库存"到 classifier |
| 暴露只读工具池给 LLM 自选 | 替 LLM 决定调哪个只读工具 |
| 写操作路由到 pending 路径 | 把读操作路由成写候选 |

**召回链路**：

```text
user_input
  ├─ RuleIntentClassifier   (寒暄/教程/代码 → no_tools)
  ├─ CandidateRetriever     (向量召回 top-K skill)
  ├─ HybridOperationRetriever (operation 级混合召回)
  ├─ expand_by_chain        (写操作扩依赖的只读链)
  └─ tool_selector          (规则筛选最终候选)
       ↓
  RouterDecision { selected_tools, risk_level, context_dependencies, fallback }
```

**目标演进**：

- 新增 **TaskState 注入**：r1 阶段就能看到 active task（修复现状缺陷）
- 新增 **Task Relevance Gate**：判断历史 task_state 是否与当前输入相关，避免污染
- 保留：风险分级 + 候选预算 + 写操作路由

**禁止演进方向**：

- 在 classifier 堆业务关键词
- 替 LLM 决定调哪个只读工具
- 用 LLM 替换规则 Router（写操作风险门禁必须确定性）

**事实**：所有「读什么」「写什么」的最终决定权在 LLM（基于工具 schema 和上下文），Router 只做**风险门禁**和**候选预算**。

### 2.2 Planner（现状缺失，目标新增）

**现状**：嵌在 Router 里的 `PlanDraft`（`runtime/planning/adapter.py`），是 RouterDecision 的结构化投影，给 Reflection 当证据用。**没有显式阶段、没有独立 trace、没有 LLM 增强**。

**目标**：独立 Stage 2，输出 `PlannerOutput`：

```python
class PlannerOutput(BaseModel):
    """Probe 已验证 LLM 能稳定输出的 schema。"""
    task_type: str          # planting_plan / crop_cycle_setup / ...
    intent: str             # 一句话业务意图
    steps: list[PlanStep]   # 拆解步骤 (id/action_type/capability/depends_on/side_effect)
```

**生成模式**：

| 模式 | 触发 | 用途 |
|---|---|---|
| `rule` | 默认 | 规则 PlanDraft,稳定基线 |
| `hybrid` | 复杂写入意图 | 规则做骨架 + LLM 增强 |

**禁止**：

- `pure_llm` 模式（LLM 完全主导）—— 写操作风险门禁必须确定性
- 把 PlannerOutput 当强约束注入 ReAct —— 退化为 workflow,丢失 ReAct 灵活性

**Probe baseline**：`backend/scripts/planner_probe.py` 实测 qwen3.6-35b-a3b 在 5 case 上 4/5 通过 4 层校验，期望 capability 命中率 90.9%。

### 2.3 PendingPlan

**位置**：`backend/app/agent/pending_plan_*.py` + `backend/app/agent/executor/pending_actions.py`

**MySQL 表**：

```text
agent_pending_plans        # 一个 plan = 一次写意图
  ├─ plan_id, farm_id, session_id
  ├─ status: pending/running/completed/cancelled/expired/failed
  ├─ current_step_index
  ├─ router_decision (快照)
  └─ expires_at            # TTL 秒级

agent_pending_plan_steps   # plan 内的若干 step
  ├─ step_id, step_index
  ├─ tool_name / skill_name
  ├─ params
  ├─ confirmation_state: pending/confirmed/rejected
  ├─ execution_status: pending/running/executed/failed
  └─ requires_confirmation
```

**写入触发**：

```text
用户「帮我创建西瓜茬口 8424」
   ↓ Router 识别 write intent
   ↓ PRE_WRITE_PLAN reflection 校验
create_pending_plan()
   ├─ step_1: 确认作物模板存在 (manage_crop_templates)
   └─ step_2: 创建茬口 (manage_crop_cycle)
   ↓
返回「需要确认」回复, 不落库
   ↓
等用户下一轮「确认」
```

**现状 = 目标**：PendingPlan 职责**不变**，是写操作的 **fail-closed 闸门**，不是规划器。即使 Stage 2 Planner 输出了多步计划，落 PendingPlan 时仍按现有规则执行。

**关键约束**：

- 写操作 Skill 默认 `requires_confirmation=True`
- 同 session 新 plan 创建时老 plan 自动 cancel（互斥）
- TTL 过期自动 expired
- 用户拒绝/取消走 `mark_step_failed` + `plan.status=cancelled`

### 2.4 Human-in-the-Loop（HITL）

**位置**：散落在 `executor/pending_actions.py` + `runtime/tool_pending.py` + `runtime/tool_pending_args.py`

**触发条件**：tool 在 `WRITE_SKILLS` 集合中（18 项）

```python
WRITE_SKILLS = frozenset({
    "create_cost_record", "create_crop_cycle", "manage_crop_cycle",
    "create_crop_template", "manage_work_orders", "create_operation_work_order",
    "settle_debt", "manage_labor_payment", "update_crop_cycle",
    "update_operation_work_order", "manage_workers", "delete_cost_record",
    "manage_cost_categories", "manage_planting_units", "manage_crop_templates",
    "manage_farm_logs", "delete_crop_cycle", "manage_user_settings",
})
```

**回环**：

```text
Round N:    用户「创建茬口 X」
              ↓ pending_plan 落表 (status=pending, confirmation_state=pending)
              ↓ Agent 回复「需要确认,计划如下...」
Round N+1:  用户「确认」 / 「取消」 / 「改一下,改成 Y」
              ↓ tool_pending 解析确认信号
              ↓ PRE_EXECUTION reflection 最终校验
              ↓ 逐 step 执行,mark_step_executed
              ↓ 全部完成 → plan.status = completed
```

**现状 = 目标**：HITL 回环机制**不变**。

**事实**：HITL 不是独立组件，是 **PendingPlan 状态机的一个外部输入**，靠 `confirmation_state` 字段驱动。

### 2.5 Reflector

**位置**：`backend/app/agent/reflector/`

**现状**：8 项 check + 5 触发点，嵌入式

```text
5 触发点:
  PRE_WRITE_PLAN     ─ router 决策写操作后,生成 pending_plan 前
  PRE_EXECUTION      ─ 用户确认后,实际执行 step 前
  POST_TOOL_RESULT   ─ 主链路最常用,LLM 最终回复前
  PRE_FINAL_RESPONSE ─ final_response 阶段
  FALLBACK_GUARD     ─ 兜底

8 项 check:
  check_no_tool_write_success_claim        (没调工具却声称写成功)
  check_pending_plan_consistency           (pending plan 一致性)
  check_required_tool_missing              (必要工具缺失)
  check_tool_failure_success_reply         (工具失败但声称成功)
  check_tool_failure_write_plan_reply      (工具失败但写计划)
  check_tool_result_discarded_reply        (工具结果被丢弃)
  check_tool_result_final_contradiction    (工具结果与最终回复矛盾)
  check_write_plan_consistency             (写计划一致性)
```

**目标新增**：

- `planner_drift` check：LLM 实际工具调用序列偏离 PlannerOutput 时记录 trace（不阻塞，仅观测）

### 2.6 Evaluation Harness

**位置**：`backend/scripts/planner_probe.py` + `app/evaluation/`（部分）

**现状**：Planner Probe 已搭好，5 case 跑通；replay 框架存在但集成度低。

**目标**：完整集成到 Stage 5，含 probe / replay / 回归门禁。

---

## 三、Harness 部件协作图

### 3.1 现状

```text
┌────────────────────────────────────────────────────────────────┐
│                       Agent Harness (现状)                      │
│                                                                │
│   ┌────────────┐   ┌────────────┐   ┌────────────────────┐    │
│   │  Rules     │   │  Skills    │   │  Prompts           │    │
│   │ (.claude/) │   │ (skill.md  │   │ (prompts/snippets) │    │
│   │            │   │  + main.py)│   │                    │    │
│   └─────┬──────┘   └─────┬──────┘   └─────────┬──────────┘    │
│         ▼                ▼                     ▼               │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              Agent Runtime (ReAct Loop)                 │  │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │  │
│   │  │ Router   │  │ Context  │  │ Memory   │              │  │
│   │  │ (规则)   │  │ Builder  │  │ Store    │              │  │
│   │  └────┬─────┘  └────┬─────┘  └────┬─────┘              │  │
│   │       ▼             ▼              ▼                    │  │
│   │  ┌─────────────────────────────────────────────────┐    │  │
│   │  │        LLM Node (主对话 LLM)                    │    │  │
│   │  └─────────────────────┬───────────────────────────┘    │  │
│   │       ┌────────────────┼────────────────┐               │  │
│   │       ▼                ▼                ▼               │  │
│   │  ┌─────────┐    ┌─────────────┐   ┌─────────────┐       │  │
│   │  │ Tool    │    │ PendingPlan │   │ Reflector   │       │  │
│   │  │Executor │    │ (写操作闸门)│   │ (8 项 check)│       │  │
│   │  └─────────┘    └─────────────┘   └─────────────┘       │  │
│   └─────────────────────────────────────────────────────────┘  │
│                        ▼                                       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Trace Collector (router/llm/tool/reflection/pending)   │  │
│   └─────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 3.2 目标（新增 Stage 2 Planner + 修复 task_state 可见性）

```text
┌────────────────────────────────────────────────────────────────┐
│                    Agent Harness (目标)                         │
│                                                                │
│   ┌────────────┐   ┌────────────┐   ┌────────────────────┐    │
│   │  Rules     │   │  Skills    │   │  Prompts           │    │
│   └─────┬──────┘   └─────┬──────┘   └─────────┬──────────┘    │
│         ▼                ▼                     ▼               │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Stage 1: Task Understanding                            │  │
│   │    Router (规则) + TaskState 注入 + Relevance Gate      │  │
│   └─────────────────────┬───────────────────────────────────┘  │
│                         ▼                                       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Stage 2: Planner (新增)                                │  │
│   │    规则 PlanDraft + LLM PlannerOutput (hybrid)          │  │
│   │    → 软提示注入 ReAct                                   │  │
│   └─────────────────────┬───────────────────────────────────┘  │
│                         ▼                                       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Stage 3: ReAct Loop                                    │  │
│   │    Context (含 plan_hint) + LLM + Tool Executor         │  │
│   │    + Reflection (5 触发点 + planner_drift)              │  │
│   └─────────────────────┬───────────────────────────────────┘  │
│                         ▼                                       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Stage 4: Write Gate (PendingPlan,不变)                 │  │
│   └─────────────────────┬───────────────────────────────────┘  │
│                         ▼                                       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Stage 5: Finalize + Evaluation Hook                    │  │
│   └─────────────────────────────────────────────────────────┘  │
│                         ▼                                       │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  Trace Collector + Evaluation Harness                   │  │
│   └─────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

### 3.3 部件职责矩阵

| 部件 | 职责 | 禁止 |
|---|---|---|
| Router | 风险门禁 + 候选预算 | 业务意图判断 |
| Planner (新) | 显式产出 PlannerOutput,软提示注入 | 强约束 ReAct |
| Context Builder | ContextBundle 组装 + 预算 + 裁剪 | Runtime 执行 |
| Memory Store | 短期/长期记忆 + observation 检索 | API 路由 |
| LLM Node | 单轮 Reasoning + tool_calls | Prompt 治理 |
| Tool Executor | 并行执行 + ToolMessage 回灌 | 业务决策 |
| PendingPlan | 写操作 fail-closed 闸门 | 任务拆解 |
| Reflector | 8 项 check 防幻觉 + 写一致性 | 业务查询 |
| Trace Collector | 链路记录 + 回放 | 业务决策 |

---

## 四、已知缺陷（现状 → 目标修复）

| # | 现状缺陷 | 影响 | 目标修复 |
|---|---|---|---|
| 1 | task_state 在 router r1 不可见 | 多轮承接失效 (playground 已观测) | Stage 1 注入 task_state preview |
| 2 | task_graph/ 1580 行未接入 | 死代码候选 | 阶段 3 决策吸收或删除 |
| 3 | task_state_updater 靠启发式 | 多数 turn 落 `no_task_state_signal` 兜底 | Stage 5 升级 hybrid updater |
| 4 | 没有显式 Planner 阶段 | trace 难读, 评测难做 | Stage 2 新增 |
| 5 | SkillRouter 对 web_search 做规则特判,误杀 BM25+向量召回 | "今天苏州西瓜价格是" 调到 get_farm_status 答非所问 | 阶段 0 删 `_allow_model_choice_read_candidate` web_search 分支 |

---

## 五、推进路径

每阶段都要求**可验证、可回滚**。

### 5.0 架构原则：SkillRouter 分层治理

SkillRouter 不应是"规则 vs BM25+向量 vs LLM 自选"三选一,而是**三层协作**。Spike 实证(2026-07-31,10 case,见 `backend/scripts/router_c_spike.py`):

| 方案 | 命中率 | web_search 命中 | 平均耗时 | LLM 成本 |
|---|---|---|---|---|
| Mode A (纯规则) | 50% | 28.6% | 0 ms | 0 |
| Mode B (LLM 自选,跳过召回) | 90% | 100% | 1936 ms | 1 次/case |
| Mode C (BM25+向量 top3,不调 LLM) | 90% (top1 仅 70%) | 100% | 2261 ms | 0 |

**结论**:**单一方案都不是最优**。Mode C top1 失败的 case (trump_news, farm_blocker) 都因 BM25 对"农场"等词法信号过敏;Mode B 准但贵;Mode A 又错过价格/政策/行情类。

**目标架构(三层)**:

```text
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: 召回 (BM25+向量)  ← 删掉业务关键词召回              │
│   HybridOperationRetriever → top-K 候选                      │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: 硬规则门禁 (保留,删业务关键词)                      │
│   - 写操作风险分级 (write_confirm/write_high) ← LLM 不能自决 │
│   - 寒暄/教程兜底 (no_tools)                                 │
│   - schema token 预算                                         │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: LLM 自选 (在 top-K 里选)  ← 删掉单工具特判         │
│   bind_tools(top-K) → LLM Reasoning → tool_calls             │
└─────────────────────────────────────────────────────────────┘
```

**禁止混淆**:Layer 2 的"硬规则"指的是**风险/兜底/预算**这类必须确定性的约束,**不是**给单个工具(如 web_search)加关键词白名单。

### 阶段 0:删 web_search 工具级特判(P0 止血,修复缺陷 #5)

**问题定位**:`app/agent/router/policy.py:407`

```python
def _allow_model_choice_read_candidate(message, candidate):
    if candidate.name != "web_search":
        return True                                    # 其他工具: LLM 自决
    return signals.looks_like_web_search(message)     # web_search: 强制规则二次校验 ← bug
```

BM25+向量已经把 web_search 召回到候选里(Layer 1 工作正常),但 policy 用 `looks_like_web_search`(纯关键词规则)做二次校验,把 web_search 踢出候选,导致 Layer 3 LLM 看不到它。

**最小改动**:

- 删除 `_allow_model_choice_read_candidate` 中 web_search 特判分支,所有 read 候选一视同仁
- (可选,止血)`WEB_CURRENT_EVENT_TOPIC_HINTS` 补"价格/行情/政策/上市"等词

**验证**:

- `backend/scripts/router_c_spike.py` 在 10 case 上跑通,Mode B 命中率 ≥ 90%
- playground session `playground-1785463980198-vw0gt9` turn 207 "今天苏州西瓜价格是" 能调到 web_search

**回滚**:恢复 `_allow_model_choice_read_candidate` 的 web_search 分支。

**后续清理**(阶段 2 一起做):删除 `looks_like_web_search` 函数本身,让 web_search 与其他 read 工具完全平等。

### 阶段 1：让 task_state 在 router r1 可见（修复缺陷 #1）

**最小改动**：在 r1 router 调用前注入 task_state preview，不引入新模块。

**验证**：playground 多轮 case 回归通过。

**回滚**：移除注入即可。

### 阶段 2：把「假 Planning」显式化（修复缺陷 #4）

**最小改动**：

- 把 `runtime/planning/adapter.py` 的 `plan_draft_from_router_decision` 提升为独立 trace 节点 `planner.draft`
- 引入 `LLMPlannerOutput` schema（参考 `backend/scripts/planner_probe.py`），让 LLM 在第一轮可选地输出结构化 plan
- PlanDraft 作为**软提示**注入 system prompt，不强制约束 ReAct

**验证**：Planner Probe 在 5 个 case 上稳定输出合法 PlanIR，`planner.draft` trace 节点完整。

**回滚**：禁用 LLM PlannerOutput 路径，保留规则 PlanDraft。

### 阶段 3：评估是否吸收 task_graph（修复缺陷 #2）

**决策点**：

- 如果阶段 2 的 LLM Planner 表现稳定（成功率 > 80%）→ 吸收 task_graph 的 slot extractor / FactSource / static validator
- 如果阶段 2 LLM Planner 失败率高 → 删除 task_graph，保留 pending_plan + task_state 即可

**禁止**：在阶段 2 验证完成前，移动 task_graph 目录或大规模重构。

---

## 六、不做的事

明确列出**不在本目标范围**的工作，避免范围蔓延：

- ❌ 多 agent 架构（业务复杂度不匹配，状态共享成本高）
- ❌ 用 LLM 替换规则 Router（写操作风险门禁必须确定性）
- ❌ 把 task_graph DAG scheduler 接入主链路（阶段 3 决策前不动）
- ❌ Plan-and-Execute 强分离（Planner 输出仅软提示，不强制约束 ReAct）
- ❌ 在 classifier 堆业务关键词修单个 case
- ❌ 让 PendingPlan 承担任务拆解职责（它是闸门不是规划器）
- ❌ 引入新的 Manager / Protocol / Plugin 抽象层

---

## 七、决策原则

新功能 X 提案时，依次问：

1. 是否修复 SkillRouter 单工具关键词特判? → 推进阶段 0
2. 是否让 task_state 在 r1 可见？ → 推进阶段 1
3. 是否让 Planner 显式化？ → 推进阶段 2
4. 是否解决 task_graph 接入决策？ → 推进阶段 3
5. 是否在第六节"不做的事"清单里？ → 拒绝
6. 是否引入新抽象层？ → 默认拒绝，需 PR 说明保留理由

只有 1-4 答 "是" 或 5-6 答 "否" 才进入实施。

**SkillRouter 改动额外检查**:任何在 router 加的关键词规则,必须问"这是 Layer 2 硬规则(风险/兜底/预算)还是 Layer 1 召回信号?"。如果是后者,应该写进 skill.md triggers 让 BM25+向量处理,而不是堆在 classifier_signals 里。

---

## 八、新成员快速上手

读 3 份文档即可对齐：

1. 本文（现状 + 目标对照）
2. [Agent 开发规范](../agent/agent-development-standard.md)（硬规范 + 模块边界）
3. [Agent Plan/Task 管理机制：两套设计记录](../design/agent-plan-mechanisms.md)（pending_plan / task_state / task_graph 现状）

跑一次 Planner Probe（理解 LLM 在 PlanIR schema 上的拆解能力 baseline）：

```bash
cd backend
.venv/bin/python -m scripts.planner_probe
```

跑一次主链路 trace 实测（playground 任意 session，按 trace node_type 顺序读）。

---

## 变更记录

| 日期 | 变更 |
|---|---|
| 2026-07-31 | 初版,基于 Planner Probe 实测结果 + 2026-07-30 收敛方案,合并现状与目标 |
| 2026-07-31 | 加入 5.0 SkillRouter 分层治理架构原则 + 阶段 0 (删 web_search 特判),基于 router_c_spike.py 10 case 实证 |
