# Agent Module Remediation Design

## 背景

`backend/app/agent/` 当前共 184 个 `.py` 文件、20,151 行代码。基于对
目录结构、文件行数、import 依赖图、空目录检测与现有 trace 的系统性扫描，
识别出以下四类与项目治理规则（[python-style.md](../../.claude/rules/python-style.md)
的"生产 Python 文件 ≤ 1000 行、500-1000 行观察"、"删除不再使用的代码"；[CLAUDE.md](../../.claude/CLAUDE.md) 的硬性规则）
冲突的问题：

1. **死代码与空目录**：`planner/` 整个包零外部引用，`response/`、`sessions/` 为空目录。
2. **超限文件**：4 个文件进入 500-1000 行观察区间或超过 1000 行硬上限，其中 2 个超 1000 行。
3. **同源碎片**：同一关注点被切成多个 ≤ 30 行的微型文件，部分仅为转发层。
4. **重复抽象**：三处 registry、三个相邻"候选/计划"模型、五处路由逻辑散落。

本设计与 [2026-07-10-skill-capability-governance-design.md](./2026-07-10-skill-capability-governance-design.md)
正交但相互引用：

- 该 spec 解决"Skill 能力治理"（业务能力粒度、Registry 事实源、路由可解释性）。
- 本 spec 解决"agent 模块自身代码治理"（死代码、超限文件、碎片化、重复抽象）。
- 两者在 Phase 4（runtime binding）有强耦合：本 spec 的 R1 阶段必须先于该 spec 的 Phase 4 完成。

## 目标

把 agent 模块从"混合了过度拆分与局部巨型文件"的状态，整理为符合当前治理规则、
关注点收敛、可支撑后续 skill-capability-governance Phase 4 落地的状态。

## 非目标

- 不变更任何对外业务行为：API 契约、Skill 输出、pending action 语义、trace 字段全部保持不变。
- 不重写业务服务层（`app/services/**` 不动）。
- 不重构 skill 内部 handler 实现（skill-capability-governance Phase 6 范围）。
- 不引入新抽象层、新框架、新依赖。
- 不解决 skill-capability-governance spec 自身的风险（评分阈值校准、embedding retrieval 等）。

## 设计原则

1. **行为保持不变**：所有整改项必须维持测试基线（现有 37 个 agent 测试 + 13 个 skill 测试）全部通过。
2. **零风险项优先**：先做删除死代码、空目录等不可逆但零风险的操作。
3. **超限文件先于功能扩展**：在 skill-capability-governance Phase 4 给 `runtime/nodes.py`、`runtime/tool_executor.py` 增加 capability 消费逻辑前，必须先拆分这两个文件。
4. **一个 PR 一个独立可验证项**：每个子任务独立 PR、独立测试、独立 review。
5. **数据驱动外移**：硬编码词库（如 `classifier.py` 的 40+ `_looks_like_*`）改为 yaml 配置，规则不丢失。
6. **三次重复再抽象**：合并重复抽象时保留必要差异，不为统一而统一。

## 整改范围

### 范围内

| 类别 | 涉及位置 |
| --- | --- |
| 死代码 | `app/agent/planner/`、`app/agent/response/`、`app/agent/sessions/` |
| 超限文件 | `runtime/tool_executor.py` (1264)、`runtime/nodes.py` (1055)、`router/classifier.py` (789)、`application/smart_fill.py` (515) |
| 同源碎片 | `application/stream_chat_*.py` 5 连号、`application/chat_use_case*.py` 2 连号、`runtime/{errors,quota,graph_factory}.py` 等 |
| 重复抽象 | 三个候选模型、五处路由逻辑、`router/registry.py` legacy fallback |

### 范围外

| 范围 | 原因 |
| --- | --- |
| `app/services/**` | 业务服务保持稳定 |
| `app/api/**` | API 契约不变 |
| `app/models/**` | 数据模型不变 |
| `app/skills/<skill-name>/scripts/main.py` 内部实现 | skill-capability-governance Phase 6 范围 |
| `app/context/**`、`app/memory/**` | 不在本整改触及层 |

## 详细整改项

整改按风险与依赖关系分 4 个阶段。每个阶段可作为独立 sprint 推进，但 R1 必须早于
skill-capability-governance Phase 4。

### Phase R0：零风险清理

完成条件：删除死代码，agent 模块减少 ≥ 70 行 + 3 个目录。

| ID | 任务 | 文件 / 目录 | 验证 |
| --- | --- | --- | --- |
| R0.1 | 删除 `planner/` 整个包 | `app/agent/planner/{__init__,intent,models}.py` (63 行) | grep 确认零外部 import；ruff + pytest 全通过 |
| R0.2 | 删除空目录 `response/` | `app/agent/response/` | 目录扫描确认无文件 |
| R0.3 | 删除空目录 `sessions/` | `app/agent/sessions/` | 目录扫描确认无文件 |
| R0.4 | 合并 `executor/tool_calls.py` 到调用方 | `app/agent/executor/tool_calls.py` (19 行 re-export) | 调用方直接从 `runtime.nodes` 导入 |

**前置确认**：R0.1 启动前需重新跑一次 `grep -rn "from app.agent.planner " app/ tests/` 确认仍为零。

### Phase R1：超限文件拆分

完成条件：生产 `.py` 文件全部低于 1000 行硬上限；500-1000 行只在职责明显混杂时继续收束；`runtime/`、`router/`、`application/` 内部职责清晰。

#### R1.1 `runtime/tool_executor.py` 拆分（1264 行 → ≤ 350 行/文件）

按职责拆为 4 个子模块，保留 `tool_executor.py` 作为编排入口：

```text
app/agent/runtime/tool_executor.py        (orchestrator, ≤ 200 行)
app/agent/runtime/tool_permission.py      (权限决策, ~150 行)
app/agent/runtime/tool_args_normalize.py  (参数归一化, ~300 行)
app/agent/runtime/tool_pending_plan.py    (pending plan 构建, ~350 行)
```

职责划分依据（基于现有 43 个私有函数的实际分布）：

| 子模块 | 承载函数（示例） |
| --- | --- |
| `tool_permission.py` | `_permission_decision`、`_PermissionDecision`、`_disabled_tool_message`、`_permission_reject_message`、`_validation_error_message` |
| `tool_args_normalize.py` | `_normalize_operation_work_order_args`、`_fill_operation_default_wage`、`_normalize_settle_labor_payment_args`、`_fill_update_crop_cycle_context_args`、`_resolve_pending_*` |
| `tool_pending_plan.py` | `_pending_plan_tool_message`、`_store_pending_plan_from_steps`、`_validated_plan_draft_*`、`_build_pending_confirmation*`、`_pending_action_message` |
| `tool_executor.py` (剩余) | 主入口 `execute_tool_calls`、reflection 拦截 `_reflection_block_message`、对外公共 API |

**测试基线**：`tests/agent/test_pending_action_executor.py`、`test_pending_plan_executor.py`、
`test_tool_executor_metadata.py` 全部保持通过，且不修改这些测试文件。

#### R1.2 `runtime/nodes.py` 拆分（1055 行 → ≤ 400 行/文件）

按 LangGraph 节点职责拆分：

```text
app/agent/runtime/nodes.py                (主节点入口, ≤ 400 行)
app/agent/runtime/nodes/llm_invoke.py     (LLM 调用与重试, ~300 行)
app/agent/runtime/nodes/context_bundle.py (上下文打包与系统提示, ~200 行)
app/agent/runtime/nodes/trace_recorders.py(trace 记录, ~200 行)
```

注意：拆分时同步收敛 [graph.py](../../backend/app/agent/graph.py) 与
[runtime/graph_factory.py](../../backend/app/agent/runtime/graph_factory.py) 的双入口
（graph.py 45 行仅为 graph_factory.py 20 行的薄壳，可合并到 graph_factory.py）。

#### R1.3 `router/classifier.py` 关键词外移（789 行 → ≤ 250 行 + yaml）

现状：1 个 `RuleIntentClassifier` 类内嵌 40+ 个 `_looks_like_*` 方法做关键词匹配，
本质是数据驱动的规则引擎被硬编码进 Python。

整改：

1. 把所有 `_looks_like_*` 方法的关键词列表抽到 `app/agent/router/rules/*.yaml`（按 domain 分文件）。
2. 保留通用匹配引擎：`_has_any`、`_extract_*` 等纯函数留下。
3. 类本身体积预计降到 ≤ 250 行。
4. 与 skill-capability-governance spec 第 636 行"减少业务硬编码"对齐——但本 spec 先做机械外移，
   不替换为 Registry-driven retrieval（后者是 governance spec Phase 3.3 的范围）。

```yaml
# app/agent/router/rules/finance.yaml 示例
finance:
  cost_summary_query:
    keywords: ["花了多少", "支出", "成本汇总"]
    anti_keywords: ["创建", "删除"]
  debt_summary_query:
    keywords: ["欠款", "赊账", "应付"]
```

#### R1.4 `application/smart_fill.py` 拆分（515 行 → ≤ 300 行/文件）

按 smart fill 的实际职责（缺参补全、上下文推断、用户追问生成）拆 2 个文件：

```text
app/application/smart_fill.py        (主入口, ≤ 300 行)
app/application/smart_fill_inference.py (上下文推断, ≤ 250 行)
```

### Phase R2：同源碎片合并

完成条件：消除 ≤ 30 行的纯切片文件；同前缀文件归并为子包或合并文件。

#### R2.1 `stream_chat_*.py` 5 连号合并为子包

现状（合计 910 行）：

| 文件 | 行数 |
| --- | --- |
| `stream_chat_use_case.py` | 460 |
| `stream_chat_finalization.py` | 248 |
| `stream_chat_persistence.py` | 79 |
| `stream_chat_types.py` | 59 |
| `stream_chat_tail.py` | 64 |

整改为：

```text
app/application/chat/stream_chat/
  __init__.py        # re-export use_case 主入口
  use_case.py        # 主流程
  finalization.py    # 收尾
  persistence.py     # trace + 持久化
  tail.py            # 尾部事件
  types.py           # 事件/状态类型
```

#### R2.2 `chat_use_case*.py` 2 连号合并

`chat_use_case.py` (214) + `chat_use_case_helpers.py` (229) = 443 行，低于 500 观察区间。
helpers 文件本质是把主类的私有方法外移，**合并回一个文件**。

#### R2.3 微型文件合并

| 现文件 | 行数 | 整改 |
| --- | --- | --- |
| `runtime/errors.py` | 8 | 合并到 `runtime/__init__.py` 或保留（待 R2.3 评审） |
| `runtime/quota.py` | 18 | 合并到 `runtime/nodes.py` 的引用方 |
| `runtime/graph_factory.py` | 20 | 合并到 `graph.py`（顶层） |
| `application/response_trace.py` | 19 | 合并到 `application/chat_use_case_helpers.py` 或独立保留 |
| `application/context_invalidation.py` | 19 | 合并到 `application/context_memory.py`（21 行） |
| `application/context_memory.py` | 21 | 同上 |
| `application/admin_config_use_case.py` | 30 | 保留（已是 use case 最小粒度） |

合并原则：合并后文件 ≤ 200 行且职责内聚；若合并后超限则保持独立。

### Phase R3：重复抽象收敛

完成条件：消除三处明显重复，但保留必要差异。

#### R3.1 三个"候选/计划"模型收敛

现状（三个相邻模型，概念有重叠）：

| 模型 | 位置 | 用途 |
| --- | --- | --- |
| `ToolCandidatePlan` | `app/agent/planner/models.py` (17 行) | 已在 R0.1 删除 |
| `ToolCandidate` | `app/agent/router/models.py` | Router 候选 |
| `PlanDraft` / `PlanStep` | `app/agent/planning/models.py` | 多步写计划 |

R0.1 删除 `planner/` 后，自然消除 `ToolCandidatePlan`。
`ToolCandidate`（路由候选）与 `PlanDraft`（执行计划）职责不同，**保留**。

#### R3.2 路由逻辑收敛

现状（5 处路由相关代码，~5900 行）：

| 位置 | 行数 | 角色 |
| --- | --- | --- |
| `tool_selector.py` | 310 | 关键词 + 链式扩展 |
| `tool_selection_rules.py` | 305 | 静态规则常量 |
| `intent_router.py` | 132 | 意图分类 |
| `router/` 整个包 | 2017 | SkillRouter / Classifier / Policy |

整改方向：

1. R3.2a：`tool_selector.py` 与 `tool_selection_rules.py` 合并为 `router/selection.py`（关键词匹配引擎 + 规则表）。
2. R3.2b：`intent_router.py` 合并到 `router/classifier.py`（同属意图识别）。
3. R3.2c：保留 `router/` 包对外接口不变。

**前置条件**：`tool_selector` 被 20+ 处测试与生产代码直接导入，收敛必须保留 re-export 兼容层
至少一个 sprint，再用 deprecation cycle 下线。

#### R3.3 `router/registry.py` legacy fallback 退场

[router/registry.py](../../backend/app/agent/router/registry.py) 注释自述："长期事实源是
`app.skills.registry`，这里只是 fallback"。但当前仍是 143 行的 `CATALOG_REGISTRY` 静态 dict。

整改（与 skill-capability-governance spec Phase 5 协调）：

1. R3.3a：列出 `CATALOG_REGISTRY` 中所有条目，逐项核对是否已在 `skills/registry/skills.yaml`。
2. R3.3b：已迁移的条目从 `CATALOG_REGISTRY` 删除，标注迁移 commit。
3. R3.3c：所有条目迁移完成后，文件降级为单函数 `default_risk_for_tool()`（如仍需保留）。
4. R3.3d：定义退场指标——`CATALOG_REGISTRY` 条目数 ≤ 0 时本文件可删除。

## 与 skill-capability-governance spec 的协调

| 本 spec 阶段 | 关联 governance spec 阶段 | 协调规则 |
| --- | --- | --- |
| R0 | 无 | 独立推进，零依赖 |
| R1.1、R1.2 | governance Phase 4.2、4.3 | **本 spec R1 必须先完成**：governance Phase 4 会向 `nodes.py`、`tool_executor.py` 新增 capability 消费逻辑，必须先有可读的子结构 |
| R1.3 | governance Phase 3.3 | 本 spec 只做机械外移到 yaml；governance spec 负责替换为 Registry-driven retrieval |
| R3.3 | governance Phase 5（governance checks） | 共用退场指标，统一在 `scripts/check-skill-registry.sh` 中检查 |
| R3.2 | 无直接关联 | 但 R3.2 完成后，governance spec 的 Router 实现会更聚焦 |

## 推荐执行顺序

按风险与依赖关系排序，建议拆成 4 个 sprint：

```text
Sprint 1 (1 周)
  └─ R0 全部 + R2.3 微型文件合并
      └─ 每个 PR ≤ 100 行变更，纯结构，零业务风险

Sprint 2 (2 周)
  └─ R1.1 + R1.2（runtime 两个超限文件拆分）
      └─ 必须先于 governance Phase 4
      └─ 每个 PR 配套 e2e 录制 baseline 行为对比

Sprint 3 (1 周)
  └─ R1.3 + R1.4（classifier 关键词外移 + smart_fill 拆分）

Sprint 4 (2 周)
  └─ R2.1 + R2.2 + R3.1（碎片合并 + 死模型消除）

Sprint 5 (按需)
  └─ R3.2 + R3.3（路由收敛 + legacy registry 退场）
      └─ 与 governance Phase 5 同步推进
```

## 改造文件边界

### 第一阶段（R0 + R2.3）必须改动

| 文件或目录 | 改造内容 | 影响面 |
| --- | --- | --- |
| `app/agent/planner/` | 删除整个包 | 零（已确认无外部引用） |
| `app/agent/response/` | 删除空目录 | 零 |
| `app/agent/sessions/` | 删除空目录 | 零 |
| `app/agent/executor/tool_calls.py` | 合并到调用方 | 1-2 个调用方更新 import |
| `app/agent/runtime/errors.py` | 合并决策（合并或保留） | 视评审而定 |
| `app/agent/runtime/quota.py` | 合并到引用方 | 1 个调用方更新 import |
| `app/agent/runtime/graph_factory.py` | 合并到 `graph.py` | 1 个调用方更新 import |

### 第二阶段（R1.1 + R1.2）必须改动

| 文件 | 改造内容 | 影响面 |
| --- | --- | --- |
| `app/agent/runtime/tool_executor.py` | 拆分为 4 个子模块，本文件保留为编排入口 | 多处 import 路径变化 |
| `app/agent/runtime/tool_permission.py` | 新建 | — |
| `app/agent/runtime/tool_args_normalize.py` | 新建 | — |
| `app/agent/runtime/tool_pending_plan.py` | 新建 | — |
| `app/agent/runtime/nodes.py` | 拆分为主文件 + 3 个 `nodes/` 子模块 | 多处 import 路径变化 |
| `app/agent/runtime/nodes/llm_invoke.py` | 新建 | — |
| `app/agent/runtime/nodes/context_bundle.py` | 新建 | — |
| `app/agent/runtime/nodes/trace_recorders.py` | 新建 | — |
| `app/agent/graph.py` | 合并 `graph_factory.py` 内容 | — |

### 第三阶段（R1.3 + R1.4）必须改动

| 文件 | 改造内容 | 影响面 |
| --- | --- | --- |
| `app/agent/router/classifier.py` | 关键词外移到 yaml，本文件保留匹配引擎 | 路由行为必须不变 |
| `app/agent/router/rules/*.yaml` | 新建（按 domain 分文件） | — |
| `app/application/smart_fill.py` | 拆分为主入口 + 推断模块 | 内部重构 |
| `app/application/smart_fill_inference.py` | 新建 | — |

### 第四阶段（R2 + R3）必须改动

| 文件或目录 | 改造内容 | 影响面 |
| --- | --- | --- |
| `app/application/chat/` | 已承接 stream/chat use case 子包；进一步合并需证明职责内聚且不超过 1000 行硬上限 | import 路径变化 |
| `app/application/chat/use_case.py` | 已承接非流式 chat use case；helpers 已归入真实子包 | 单文件变更 |
| 旧 application 根兼容入口 | 已删除，不再作为后续改造对象 | — |
| `app/agent/router/selection.py` | 合并 tool_selector + tool_selection_rules | 保留 re-export 兼容层 |
| `app/agent/tool_selector.py` | 降级为 re-export，后续下线 | 20+ 处 import 兼容 |
| `app/agent/tool_selection_rules.py` | 同上 | — |
| `app/agent/router/registry.py` | 逐项迁移到 skills/registry 后下线 | 与 governance Phase 5 协调 |

### 明确不改

| 范围 | 原因 |
| --- | --- |
| `app/services/**` | 业务服务保持稳定 |
| `app/api/**` | API 契约不变 |
| `app/models/**` | 数据模型不变 |
| `app/skills/<skill-name>/scripts/main.py` | skill handler 重构属于 governance Phase 6 |
| `app/skills/registry/` | 已由 governance Phase 1 完成建设 |
| 现有 trace payload 字段 | 行为不变约束 |

## 验收标准

### 硬性指标

- [ ] `app/agent/` 内所有 `.py` 文件 ≤ 1000 行；500-1000 行需按职责混杂度评审（`find app/agent -name "*.py" -exec wc -l {} + | sort -n` 检查）
- [ ] `app/agent/` 内方法建议 ≤ 50 行，超过 80 行需说明或拆成步骤函数
- [ ] 零空目录：`find app/agent -type d -empty` 返回空
- [ ] `planner/` 包完全删除
- [ ] `app/agent/` 内零外部引用的死代码（通过 `grep -rn "from app.agent.X " app/ tests/` 反向核对）

### 测试指标

- [ ] 现有 37 个 agent 测试全部通过：`pytest backend/tests/agent -v`
- [ ] 现有 13 个 skill 测试全部通过：`pytest backend/tests/skills -v`
- [ ] Router eval baseline 指标不下降：`pytest backend/tests/evaluation -v`

### 行为一致性指标

- [ ] 同一组用户输入（10 条黄金 case）的 RouterDecision 输出在整改前后字段级一致
- [ ] 同一组用户输入的最终回复文本一致（除可接受的 trace 字段顺序差异）
- [ ] pending action 创建/确认/取消语义不变

### 工程指标

- [ ] `ruff check backend/app/agent` 零告警
- [ ] `bash scripts/check-complexity-budget.sh` 通过
- [ ] `bash scripts/check-layer-deps.sh` 通过

## 测试计划

### 单元测试

每个 R 阶段子任务独立维护或扩展单元测试：

| 阶段 | 测试要求 |
| --- | --- |
| R0 | 仅删除/合并，现有测试不变；删除 `planner/` 时同步删 `tests/agent/test_planner_*`（如有） |
| R1.1、R1.2 | 拆分时**禁止修改**现有测试断言；只能调整 import 路径 |
| R1.3 | 关键词外移后，所有 `tests/agent/router/test_classifier*.py` 必须保持原断言通过 |
| R2、R3 | 合并后调用方测试保持不变 |

### 行为基线测试

在 R1 启动**前**录制一次基线：

```bash
# 用 10 条黄金输入跑 Router，保存 RouterDecision 完整 payload
pytest backend/tests/agent/router/test_skill_router.py \
       --record-baseline=tests/agent/router/baseline_r1.json
```

R1 完成后用同一组输入对比：

```bash
pytest backend/tests/agent/router/test_skill_router.py \
       --compare-baseline=tests/agent/router/baseline_r1.json
```

任何字段级差异必须人工 review 后才能合并。

### 回归检查

| 检查项 | 命令 | 频率 |
| --- | --- | --- |
| 单元测试 | `pytest backend/tests/agent backend/tests/skills -v` | 每个 PR |
| 复杂度预算 | `bash scripts/check-complexity-budget.sh` | 每个 PR |
| 层级依赖 | `bash scripts/check-layer-deps.sh` | 每个 PR |
| Lint | `ruff check backend/app/agent && ruff format --check backend/app/agent` | 每个 PR |
| Harness 全量 | `bash scripts/harness-check.sh` | 每个 sprint 末 |

## 风险与缓解

### 风险 R1：拆分超限文件时误改逻辑

**场景**：`tool_executor.py` 拆 4 个子模块时，某个私有函数的副作用被无意识改变。

**缓解**：
1. 拆分前先录制行为基线（见测试计划）。
2. 每个 R1 子任务单独 PR，禁止 batch 多文件拆分。
3. PR 描述必须列出"函数迁移映射表"：原函数 → 新位置。
4. 至少 1 名 reviewer 对照映射表逐函数核对。

### 风险 R2：关键词外移时漏迁规则

**场景**：`classifier.py` 的 40+ `_looks_like_*` 方法迁移到 yaml 时漏掉某个关键词。

**缓解**：
1. 迁移完成后跑 `tests/agent/router/test_classifier*.py`，必须零修改断言通过。
2. 用 `git log` 反查近 6 个月用户实际输入（trace 中），抽样 50 条做端到端验证。
3. yaml 文件按 domain 拆分，单个 yaml ≤ 50 行，便于 review。

### 风险 R3：兼容层下线周期不可控

**场景**：R3.2a 把 `tool_selector.py` 改为 re-export，但下线时间无明确 deadline，导致兼容层永久存续。

**缓解**：
1. 兼容层加上 `# DEPRECATED: 待 <日期> 删除` 注释。
2. 在 `scripts/check-complexity-budget.sh` 中加兼容层过期检查。
3. 设置 deprecation 上限：兼容层最多存在 2 个 sprint，第 3 个 sprint 必须删除。

### 风险 R4：与 governance Phase 4 节奏冲突

**场景**：本 spec R1 未完成时 governance Phase 4 启动，两边同时改 `runtime/nodes.py`。

**缓解**：
1. 本 spec R1.1、R1.2 标记为 governance Phase 4 的**硬前置**。
2. 在 governance `tasks.md` 的 Phase 4 顶部加 `depends-on: agent-module-remediation R1.1, R1.2`。
3. 两个 spec 的 PR 互不交叉，按时间窗串行。

### 风险 R5：合并 `stream_chat_*` 时遗漏事件顺序

**场景**：stream chat 涉及 SSE 事件流，合并文件时事件发送顺序错乱。

**缓解**：
1. 合并前用 `tests/agent/test_stream_chat*.py`（如无则新建）录制一组 SSE 事件序列。
2. 合并后对比事件序列字节级一致。

## 度量与监控

### 整改前 baseline（待 R0 启动前固化）

| 指标 | 当前值 | 目标值 |
| --- | --- | --- |
| `app/agent/` 文件数 | 184 | ≤ 175 |
| `app/agent/` 总行数 | 20,151 | ≤ 18,000 |
| 最大文件行数 | 1264 (`tool_executor.py`) | ≤ 1000 |
| 硬超限文件数（> 1000） | 2 | 0 |
| 空目录数 | 2 | 0 |
| 死代码包数 | 1 (`planner/`) | 0 |
| 路由关注点散落处 | 5 | ≤ 2 |
| Registry 重复处 | 3 | 1 |

### 月度跟踪

每月末 sprint review 时输出：

- 本月完成的 R 阶段。
- 文件行数分布变化（最大值、P50、P95）。
- 测试基线通过率。
- 与 governance spec 的协调进度。

## 决策摘要

采用**纯结构整改、行为不变、阶段独立推进**的策略。短期先清理零风险死代码与空目录；
中期把 4 个超限文件拆分为可读子模块，为 skill-capability-governance Phase 4 铺路；
长期收敛重复抽象与同源碎片。整套整改保持业务行为字节级一致，所有改动可独立 review、
独立 revert、独立验证。
