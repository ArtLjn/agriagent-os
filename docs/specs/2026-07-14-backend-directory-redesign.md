---
last_updated: 2026-07-17
status: draft
---

# 后端目录重设计 spec

## 文档信息

| 项 | 内容 |
| --- | --- |
| 路径 | [docs/specs/2026-07-14-backend-directory-redesign.md](./2026-07-14-backend-directory-redesign.md) |
| 创建日期 | 2026-07-14 |
| 状态 | draft（待评审） |
| 关联诊断 | [2026-07-12-backend-bloat-diagnosis.md](./2026-07-12-backend-bloat-diagnosis.md)（诊断与整改追踪） |
| 关联 spec | [2026-07-12-agent-module-remediation.md](./2026-07-12-agent-module-remediation.md)（agent 模块整改） |
| 关联架构 | [../architecture/boundaries.md](../architecture/boundaries.md)、[../architecture/overview.md](../architecture/overview.md) |

本 spec 给出 backend 目录的目标态设计与迁移路径。诊断与 23 项整改追踪由
[backend-bloat-diagnosis.md](./2026-07-12-backend-bloat-diagnosis.md) 承载；
本 spec 承载**目标架构决策**与**目录级迁移路径**，两者互补。

---

## 1. 背景

### 1.1 现状

backend/app 共 450 个 `.py` 文件、61,248 行代码（2026-07-12 快照）。开发者反馈
"agent 很难用、越写越沉重、无法维护"。诊断报告已识别 9 类问题（见
[backend-bloat-diagnosis.md 发现 1-9](./2026-07-12-backend-bloat-diagnosis.md#关键发现)）。

### 1.2 根因

沉重感不是单点问题，而是 5 个结构性因素叠加：

| 因素 | 表现 |
| --- | --- |
| **业务主线与 agent 框架耦合** | `agent/` 184 文件里混了 use case、business output、evaluation 等业务主线 |
| **非主线子系统污染主线** | `evaluation/`（24 文件）和 `modules/data_flywheel/`（27 文件）共占 18.7% 代码，但都不在用户请求主链路 |
| **过度设计** | 22 个 Protocol/ABC、`ContextSelector` 重复定义、document_repository 16 个实现类（实际只用 mongo） |
| **碎片化** | 43 个 ≤30 行的微型文件、`stream_chat_*` 5 文件切片、`planner/` 死目录与 `planning/` 命名混淆 |
| **冗余依赖** | 单 agent 系统用了 LangGraph 多 agent 编排框架 |

### 1.3 为什么现在做

- 诊断已完成（2026-07-12）
- 整改追踪表已建立（2026-07-14）
- 多次讨论收敛到 5 个独立设计决策
- 继续叠加补丁只会让结构问题更难逆转

---

## 2. 设计目标

| 目标 | 衡量标准 |
| --- | --- |
| **业务主线与 agent 框架解耦** | `agent/` 文件数从 184 降到 ~30；agent 框架 0 业务 import |
| **非主线子系统隔离** | `evaluation/` 与 `data_flywheel/` 收敛到 `platforms/`，主线 app/ 不含工程基础设施 |
| **删除过度设计** | Protocol/ABC 数量减半；单实现 Protocol 全删；document_repository 16 类降至 4 类 |
| **删除冗余依赖** | 移除 LangGraph；保留仍被 StructuredTool / Message 类型使用的 langchain-core；评估兼容层（compat.py）是否仍必要 |
| **不破坏运行时行为** | 所有迁移步骤行为等价，CI 全绿，可独立回滚 |

---

## 3. 设计原则

1. **主线与子系统分离**：用户请求主链路上的代码集中可见；非主线能力单独成包
2. **agent 框架稳定、业务可膨胀**：框架不因新增 skill 而改；skill 不污染框架
3. **优先级：删除 > 合并 > 拆分 > 新建**：本阶段不新增业务能力或抽象；允许为迁移既有代码创建目标目录
4. **YAGNI**：单实现不抽象、未使用特性不保留、为未来设计的层一律收敛
5. **单进程部署不变**：本轮不拆服务，仅重组目录与依赖
6. **小步迁移**：每个决策拆为可独立 PR 的步骤，可独立回滚

---

## 4. 目标架构

### 4.1 顶层目录树

```text
backend/app/
│
├── bootstrap/                    # 应用工厂、路由注册、lifespan、middleware
├── api/                          # HTTP 路由、请求校验、依赖注入
│
├── agent/                        # 🎯 纯 agent 框架（~30 文件，稳定）
│   ├── runtime/                  # 图执行循环、节点、状态机（移除 LangGraph）
│   ├── router/                   # 意图分类、policy、registry、tool_selector
│   ├── executor/                 # skill 调用、权限、参数校验
│   ├── reflector/                # 反思
│   ├── guardrails/               # 守卫
│   ├── graph.py                  # 主入口（兼容旧路径）
│   ├── state.py                  # runtime state 类型
│   └── ports.py                  # agent 对外端口
│
├── application/                  # 🆕 业务 use case（编排 agent 完成业务流程）
│   ├── chat/                     # use_case + stream_chat + helpers
│   ├── session/                  # history + flywheel + summary
│   ├── advice/                   # advisor + use_case
│   ├── smart_fill.py
│   ├── report.py
│   ├── skill_catalog.py
│   ├── admin_config.py
│   └── pending_responses.py
│
├── skills/                       # 🆕 业务能力 skill（19 个目录，持续增长）
│   ├── manage-cost/
│   ├── manage-crop-cycle/
│   ├── weather/
│   ├── ...                       # 其余 16 个 skill
│   └── registry/                 # skill 元数据注册
│
├── modules/                      # 业务模块
│   ├── auth/
│   └── farm/
│
├── services/                     # 业务 service（CRUD 实现，P2-3 评审后可能再瘦身）
│
├── context/                      # Context 工程
├── memory/                       # Memory 工程
├── prompt/                       # Prompt 工程
├── observability/                # 观测（合并碎片后单文件）
├── simulation/                   # 仿真
│
├── core/                         # 配置、数据库、安全、llm 客户端
├── infra/                        # 基础设施（删除反向依赖后）
├── models/                       # SQLAlchemy
├── schemas/                      # Pydantic
│
└── platforms/                    # 🆕 非主线子系统
    ├── shared/                   # 打破循环依赖的共享层
    │   ├── judge_service.py
    │   └── repository_selector.py
    ├── evaluation/               # 从 app/evaluation/ 迁入
    └── data_flywheel/            # 从 app/modules/data_flywheel/ 迁入
```

### 4.2 依赖方向

```text
api  →  application/ 或 modules/*/router
            │
            ▼
     application/  ──→  agent/、context/、memory/、prompt/、modules/、services/
                            │
                            ▼
                        agent/  ──→  core/、models/、infra/
                            │
                            ▼
                agent/executor  ──→  skills/registry（不直接 import 具体 skill）
                                            │
                                            ▼
                                       skills/  ──→  services/、models/
```

### 4.3 关键依赖约束

| 约束 | 说明 |
| --- | --- |
| `agent/` 不得 import `skills/` 或 `application/` | agent 框架与业务侧解耦；通过 registry/port 间接调用 |
| `skills/` 不得 import `agent/` | skill 是被调方，不应反向依赖框架 |
| `application/` 是唯一可同时调 agent 和 skills 的层 | 业务编排的唯一入口 |
| `infra/` 不得 import `modules/` 或 `platforms/` | 修复反向依赖（infra/repository_runtime 当前违规） |
| `evaluation` 与 `data_flywheel` 不得循环 import | 共享部分提到 `platforms/shared/` |
| `agent/runtime/` 不得 import `app.memory`、`app.context.*`、`app.prompt.*` | 沿用 boundaries.md 现有规则 |

### 4.4 文件数预算

| 模块 | 当前 | 目标 | 备注 |
| --- | --- | --- | --- |
| `agent/` | 184 | **~30** | 业务主线与 skills 全部迁出 |
| `application/` | 0 | ~15 | 新建，从 agent/application/ 迁入 |
| `skills/` | 0 | ~100 | 新建，从 agent/skills/ 迁入 |
| `modules/data_flywheel/` → `platforms/data_flywheel/` | 27 | ~15 | 切片收回 + 删除 12 个未用 backend |
| `evaluation/` → `platforms/evaluation/` | 24 | ~20 | 合并微型文件 |
| `services/` | 40 | ~30 | P2-3 评审合并 |
| `infra/` | 25 | ~22 | 修反向依赖 + 合并双胞胎文件 |
| **backend/app 总计** | **450** | **~350** | 减少 ~22% |

---

## 5. 关键设计决策

### 5.1 决策 A：拆分 `platforms/`（evaluation + data_flywheel 独立）

#### 现状与问题

`app/evaluation/`（24 文件 2,414 行）与 `app/modules/data_flywheel/`（27 文件 9,034 行）
合计 51 文件 / 11,448 行，占总代码 **18.7%**，但都不在用户请求主链路上：

- evaluation 真实代码已迁入 `app.platforms.evaluation`，生产调用方改用新路径；
  `app.evaluation` 仅保留兼容入口
- data_flywheel 真实代码已迁入 `app.platforms.data_flywheel`，仅通过
  `bootstrap/routes.py` 注册 4 个 router（HTTP 入口）
- A1/A2 前置后，evaluation 与 data_flywheel 已共同依赖
  `app.platforms.shared.judge_service`，不再由 evaluation 反向 import
  `app.modules.data_flywheel.judge_service`
- A3 评估后，`rule_engine.py` 当前没有被 `platforms/data_flywheel` 直接依赖，
  暂不迁入 shared；A4 后 `services/agent_turn_service.py` 的运行时导入已指向
  `app.platforms.evaluation.discovery`
- `infra/repository_runtime.py` 已改用 `app.platforms.shared.repository_selector`，
  不再直接 import DataFlywheel 真实实现。

#### 目标

```text
app/platforms/
├── shared/                       # 🆕 共享层，打破循环依赖
│   ├── judge_service.py          # OpenAIDataFlywheelJudgeClient 提取至此
│   ├── repository_selector.py    # build_data_flywheel_repository 提取至此
│   └── rule_engine.py            # 如 evaluation 与 data_flywheel 共享则提取至此
├── evaluation/                   # 从 app/evaluation/ 整体迁入
│   ├── cases/
│   ├── metrics/
│   ├── replay/
│   ├── reports/
│   ├── runners/
│   └── discovery/
└── data_flywheel/                # 从 app/modules/data_flywheel/ 整体迁入
    ├── routers/                  # 整合 4 个 router
    ├── services/                 # 整合 service + repository（P2-1 完成后）
    └── repositories/             # 仅保留 mongo backend（删除 12 个未用类）
```

#### 前置工作（必须先做）

| 步 | 动作 | 验证 |
| --- | --- | --- |
| A1 | 抽 `judge_service` 到 `platforms/shared/` | evaluation 与 data_flywheel 改 import；CI 全绿 |
| A2 | 抽 `repository_selector` 到 `platforms/shared/`；修复 `infra/repository_runtime.py` 反向调用 | 反向 import 检查通过；CI 全绿 |
| A3 | 评估 `rule_engine` 是否需要共享 | 若 evaluation 与 data_flywheel 都用，提取到 shared |

#### 2026-07-17 前置层落地状态

- `app.platforms.shared.judge_service` 已承载 DataFlywheel judge 真实实现；
  `app.modules.data_flywheel.judge_service` 通过旧路径兼容 alias 映射到同一模块对象，
  旧 import API 不变。
- `app.platforms.shared.repository_selector` 已承载
  `build_data_flywheel_repository`；`infra/repository_runtime.py` 通过 shared selector
  创建 data_flywheel 文档仓库，消除 infra → DataFlywheel 真实目录的反向依赖。
- `app.platforms.data_flywheel` 已承载 DataFlywheel 真实代码；shared selector 已改向
  `app.platforms.data_flywheel.document_repository_*` 实现类，A1-A3 的迁移期旧路径依赖已解除。
- `app.platforms.data_flywheel.review_issue_chain` 与
  `app.platforms.data_flywheel.repair_pack` 已承载问题链与 repair pack 子域真实代码；
  原 data_flywheel root 下的 `review_issue_chain_*` / `repair_pack_*` 文件仅保留兼容入口。
- `app.modules.data_flywheel` 仅保留兼容入口，用于旧动态 import 与 monkeypatch target。
- `rule_engine.py` 暂不迁移：当前没有 data_flywheel 直接依赖，只有 evaluation
  discovery 自身测试与 `services/agent_turn_service.py` 的运行时评估入口使用。

#### 迁移步骤

| 步 | 动作 | 风险 |
| --- | --- | --- |
| A4 | `git mv app/evaluation app/platforms/evaluation` + 全局搜替换 import；保留 `app.evaluation` 兼容 alias | ✅ PR #17 |
| A5 | `git mv app/modules/data_flywheel app/platforms/data_flywheel` + 全局搜替换 import；保留 `app.modules.data_flywheel` 兼容 alias | ✅ PR #18 |
| A6 | 更新 [boundaries.md](../architecture/boundaries.md) 中相关章节 | ✅ PR #18 |

---

### 5.2 决策 B：`agent/` 瘦身

#### 现状与问题

`agent/` 184 文件混了 3 类本不属于"agent 框架"的内容：

| 类别 | 文件 | 行数 |
| --- | --- | --- |
| **业务 use case** | `application/*` 19 个文件（chat / stream_chat / history / session / smart_fill / advice / report / skill_catalog） | 3,200+ |
| **业务输出** | `advisor.py`、`report.py` | 461 |
| **评测** | `skill_coverage.py` | 375 |
| **工具选择**（属 router 范畴） | `intent_router.py`、`tool_selector.py`、`tool_selection_rules.py` | 653 |
| **基础设施** | `llm.py`、`assistant_roles.py` | 159 |
| **死代码 / 命名混淆** | `planner/`（63 行，删除候选）、`planning/`（PlanDraft / DomainValidator，运行时仍使用） | 223 |

#### 目标

`agent/` 仅保留纯框架能力（~30 文件）：

```text
agent/
├── runtime/         # 图执行、节点、状态机
├── router/          # 意图分类、policy、registry、tool_selector（合并自根目录）
├── executor/        # skill 调用、权限
├── reflector/
├── guardrails/
├── graph.py
├── state.py
└── ports.py
```

#### 文件归位表

| 来源 | 目标 | 关联整改项 |
| --- | --- | --- |
| `agent/application/*` | `app/application/` | 决策 D |
| `agent/skills/*` | `app/skills/` | 决策 C |
| `agent/advisor.py` | 已随 D3 归入 `app/application/advice/advisor.py`；`app.agent.advisor` 保留同模块对象兼容入口 | 新增 |
| `agent/report.py` | 已随 D1-D2 迁至 `app/application/report.py` | 新增 |
| `agent/skill_coverage.py` | 已随 A4 迁至 `app/platforms/evaluation/skill_coverage.py`；`agent/skill_coverage.py` 仅保留兼容入口 | 决策 A |
| `agent/intent_router.py` | `agent/router/intent.py` | 新增 |
| `agent/tool_selector.py` | `agent/router/tool_selector.py` | 新增 |
| `agent/tool_selection_rules.py` | `agent/router/rules.py` | 新增 |
| `agent/llm.py` | `core/llm.py` | 新增 |
| `agent/assistant_roles.py` | `core/settings/roles.py` | 新增，本轮按既有 `core/settings/` 包落位 |
| `agent/planner/` | 删除 | P0-1 |
| `agent/planning/` | 已迁移/收敛到 `agent/runtime/planning/`，保留现有 PlanDraft 语义 | P0-2 |

#### 迁移步骤

| 步 | 动作 | 风险 |
| --- | --- | --- |
| B1 | 删 `agent/planner/`（0 外部引用，当前工作树已无版本目录） | 低 |
| B2 | 已迁移/收拢 `agent/planning/` 到 `agent/runtime/planning/`，保留 PlanDraft / DomainValidator 语义 | 中 |
| B3 | 业务根文件归位（advisor / report / skill_coverage / intent_router / tool_selector / tool_selection_rules / llm / assistant_roles）；已完成 routing/core 子集与 `advisor` / `report` / `skill_coverage` 阶段性归位，并保留旧路径兼容入口；`graph` / `state` / `ports` 属 runtime 根文件，留给 P1-6/P1-runtime 后续处理 | 中 |
| B4 | `application/` 与 `skills/` 的迁移见决策 C、D | 见对应章节 |

---

### 5.3 决策 C：`skills/` 拆出（与 agent 平级）

#### 现状与问题

- 19 个 skill 目录位于 `agent/skills/`
- 每个 skill 是业务能力的封装（实现 CRUD、调 service），不是 agent 框架
- skill 会随业务扩张持续增长，留在 agent/ 里框架与业务永远搅在一起

#### 目标

```text
app/skills/                       # 🆕 顶层包，与 agent/ 平级
├── manage-cost/
│   ├── __init__.py
│   ├── skill.md
│   └── scripts/
│       └── main.py
├── manage-crop-cycle/
├── weather/
├── ...                           # 其余 16 个 skill
└── registry/                     # 从 agent/skills/registry/ 迁入
    ├── __init__.py
    ├── skills.yaml
    ├── aliases.yaml
    └── governance.py
```

#### 设计约束

- `agent/executor/` 通过 `skills/registry` 加载 skill 元数据与实例，**不直接 import 具体 skill 模块**
- `skills/` 实现 skill 协议（skill.md frontmatter 定义），通过注册到 registry 被 agent 调用
- skill 内部 import `services/`、`models/`，**不得 import `agent/`**

#### 迁移步骤

| 步 | 动作 | 风险 |
| --- | --- | --- |
| C0 | 已完成的迁移期兼容别名或 re-export，曾覆盖动态 import 与 monkeypatch 路径 | 中 |
| C1 | `git mv app/agent/skills app/skills` | 中 |
| C2 | 分批搜替换旧 agent skills import 与动态 import 字符串 → `app.skills` | 中 |
| C3 | 核对 `agent/executor/` 是否仍能通过 registry 加载（不直接 import） | 中 |
| C4 | 测试全部切到新路径后，移除旧 agent skills 兼容层 | 低 |

---

### 5.4 决策 D：新建 `application/`（业务 use case 层）

#### 现状与问题

业务 use case 在 D1-D2 迁移前位于 `agent/application/`（19 文件 3,200+ 行），与 agent 框架耦合：
- `chat_use_case.py` 调用 agent 完成"聊天"业务流程
- `stream_chat_use_case.py` 流式聊天
- `history_use_case.py` 历史查询
- `session_flywheel.py` 会话级数据飞轮触发
- `smart_fill.py`（515 行）智能填充
- `advice_use_case.py` + `advisor.py` 每日建议
- `report.py` 报告生成
- `skill_catalog.py` 能力菜单

这些是"用 agent 能力组合成的业务流程"，**不是 agent 框架本身**。

#### 目标

```text
app/application/                  # 🆕 业务编排层
├── chat/                         # 非流式聊天、流式聊天与聊天辅助
│   ├── use_case.py
│   ├── stream_chat.py
│   ├── stream_finalization.py
│   ├── stream_persistence.py
│   ├── stream_tail.py
│   ├── stream_types.py
│   └── helpers.py
├── session/                      # 历史与会话管理
│   ├── history.py
│   ├── flywheel.py
│   └── summary.py
├── advice/                       # 每日建议
│   ├── advisor.py
│   └── use_case.py
├── smart_fill.py
├── report.py
├── skill_catalog.py
├── admin_config.py
└── pending_responses.py
```

#### 设计约束

- `app/application/` 是 **唯一** 可同时 import `agent/` 与 `skills/` 的层
- `api/` 只能调 `application/` 或 `modules/*/router`，不能直接调 `agent/runtime/`
- `application/` 内部 use case 之间尽量不互相 import；横切共享放 `application/_shared/`

#### 同时合并的碎片

| 当前 | 目标 |
| --- | --- |
| `stream_chat_use_case.py` (460) + `stream_chat_finalization.py` (248) + `stream_chat_persistence.py` (79) + `stream_chat_tail.py` (64) + `stream_chat_types.py` (59) | 已归位到 `chat/stream_chat.py`、`chat/stream_finalization.py`、`chat/stream_persistence.py`、`chat/stream_tail.py`、`chat/stream_types.py`；进一步合并需先拆职责，避免单文件超过 500 行 |
| `chat_use_case.py` + `chat_use_case_helpers.py` | `chat/use_case.py` + `chat/helpers.py` |
| `context_invalidation.py` (19) + `context_memory.py` (21) + `response_trace.py` (19) | 并入 `chat/helpers.py` |
| `history_use_case.py` + `session_flywheel.py` + `session_summary.py` | `session/` 目录 |

#### 迁移步骤

| 步 | 动作 | 风险 |
| --- | --- | --- |
| D0 | 已完成的迁移期兼容别名或 re-export，曾覆盖 API、测试和动态 patch 路径 | 中 |
| D1 | `git mv app/agent/application app/application` | 中 |
| D2 | 分批搜替换旧 agent application import 与动态 import 字符串 → `app.application` | 中 |
| D3 | 内部重组：合并 3 个 context 碎片、按业务子目录归位；`stream_chat_*` 先归入 `chat/`，进一步合并待后续拆职责后处理 | 中 |
| D4 | 测试全部切到新路径后，移除旧 agent application 兼容层 | 低 |

D1-D2 已在 2026-07-17 PR #18 迁移中完成：真实业务 use case 目录已迁至
`app/application/`，生产代码和测试引用真实新路径。D3 第一阶段已完成
`chat/`、`session/`、`advice/` 子包归位。本轮完成 C4/D4，旧 agent
application、旧 agent skills 与旧 application 根 use case 兼容入口均已删除；
旧路径不再作为 import 或 monkeypatch 契约。`stream_chat_*` 进一步合并会超过
500 行预算，后续需先拆分职责再收敛。

---

### 5.5 决策 E：移除 LangGraph

#### 现状与问题

整个 backend 仅 **5 处 import** LangGraph，集中在 3 个文件：

| 文件 | 用途 |
| --- | --- |
| `agent/runtime/graph_factory.py` | 定义 StateGraph（2 节点 + 1 条件 + 1 回边） |
| `agent/runtime/nodes.py` | 节点函数 |
| `agent/state.py` | AgentState（TypedDict） |
| `agent/advisor.py`、`bootstrap/exceptions.py` | 类型引用 |

**实际图结构**（[graph_factory.py](../../backend/app/agent/runtime/graph_factory.py)）：

```python
graph = StateGraph(AgentState)
graph.add_node("llm", _llm_node)
graph.add_node("tools", _parallel_tool_node)
graph.set_entry_point("llm")
graph.add_conditional_edges("llm", _should_continue, {"tools": "tools", END: END})
graph.add_edge("tools", "llm")
return graph.compile()
```

这是标准 **ReAct 模式的最小循环**。LangGraph 的高级特性全部未使用：

| 特性 | 使用情况 |
| --- | --- |
| Checkpointing（中断恢复） | ❌ |
| Subgraphs（多 agent） | ❌ |
| Streaming events 复杂语义 | ❌（用普通 async/SSE） |
| Human-in-the-loop | ❌（项目自己的 pending_actions） |
| Multi-agent 协作 | ❌ |
| 时间旅行 / 分支 | ❌ |

#### 目标

用 50 行纯 Python 替换：

```python
# agent/runtime/loop.py
async def run_agent_loop(state: AgentState, max_steps: int = 15) -> AgentState:
    for step in range(max_steps):
        state = await llm_step(state)
        if not has_tool_calls(state):
            return state
        state = await execute_tools_parallel(state)
    return state
```

#### 替换前需要核对

| 点 | 当前实现 | 替换策略 |
| --- | --- | --- |
| 流式输出 | `stream_chat_use_case.py` 460 行 | 核对是否依赖 `astream_events`；若是，改 `async for chunk in llm.astream()` |
| 并行工具调用 | `_parallel_tool_node` | 用 `asyncio.gather` 直接并行 |
| Trace/重放 | `evaluation/replay/` | 项目已有 `trace_records`，核对是否依赖 LangGraph 内部状态 |

#### 迁移步骤

| 步 | 动作 | 风险 |
| --- | --- | --- |
| E1 | 实现 `agent/runtime/loop.py` 等价 ReAct 循环 | 中 |
| E2 | 替换 `graph_factory.compile_advisor_graph()` 调用方为 `run_agent_loop()` | 中 |
| E3 | 核对流式输出与 trace 重放是否行为等价 | 中 |
| E4 | 删除 `requirements.txt` 中 `langgraph` 依赖；`langchain-core` 仅在 StructuredTool / Message 类型替换后再评估删除 | 低 |

---

## 6. 迁移路径（分阶段总览）

### 6.1 阶段 P0：删除与零风险合并（第 1 周）

| 编号 | 动作 | 来源 | 状态 | 验证方式 |
| --- | --- | --- | --- | --- |
| P0-1 | 删 `agent/planner/`（死代码） | 决策 B | ✅ | `rg "app\.agent\.planner|agent\.planner" backend/app backend/tests` 返回空；本工作树待提交 |
| P0-2 | 评估并迁移/收拢 `agent/planning/` | 决策 B | ✅ | 已迁到 `agent/runtime/planning/`；`PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/agent/planning/test_plan_draft_models.py::test_runtime_planning_exports_plan_draft_contract -q` 通过；本工作树待提交 |
| P0-3 | 合并 `ContextSelector` 双定义 | diagnosis 9-#1 | ✅ e481ee56 | `ContextSelector` 仅保留 `app.context.policy.ContextSelector`；builder 只在 `TYPE_CHECKING` 下引用；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/context/test_context_selector_protocol.py -q` 通过；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/context/test_context_selector_protocol.py tests/agent/test_chat_use_case.py -q` 因本地 MySQL `localhost:3306` 不可用失败（11 failed, 10 passed）；`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` 通过 |
| P0-4 | 合并 runtime 顶部 3 碎片 | diagnosis 7 | ✅ 568529e7 | 合并为 `agent/runtime/support.py`，旧碎片已删除且旧 import 搜索为空；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/runtime/test_runtime_support.py -q` 通过；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/runtime/test_runtime_support.py tests/agent/test_chat_use_case.py -q` 因本地 MySQL `localhost:3306` 不可用失败（11 failed, 10 passed）；`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` 通过 |
| P0-5 | 合并 `observability/` 3 文件 | diagnosis 8.3 | ✅ 54960408 | 平铺为 `observability.py` 单文件；旧 `app.observability.lifecycle/metrics` import 搜索为空；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/observability/test_observability_module.py -q` 通过；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/memory/test_maybe_summarize.py tests/memory/test_summarizer.py tests/evaluation/test_trace_events.py -q` 通过；`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` 通过（复杂度检查保留既有警告） |
| P0-6 | 合并 `agent/application/` 3 碎片 | diagnosis 7 | ✅ a7f23c6a | 已并入 `agent/application/chat_use_case_helpers.py`，旧碎片已删除且旧 import 搜索为空；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/application/test_chat_runtime_helpers.py tests/agent/test_response_trace.py -q` 通过；`PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider tests/agent/test_chat_use_case.py -q` 因本地 MySQL `localhost:3306` 不可用失败（11 failed, 8 passed）；`ruff check backend/app backend/tests`、`bash scripts/check-complexity-budget.sh` 通过（复杂度检查保留既有警告） |

### 6.2 阶段 P1：核心结构迁移（第 2-3 周）

| 编号 | 动作 | 来源 |
| --- | --- | --- |
| P1-1 | 删单实现 Protocol（`MemoryServicePort`、`_ComparableStage`） | diagnosis 9-#4、9-#6 |
| P1-2 | 评估 `core/compat.py` 是否仍必要 | diagnosis 9-#8 |
| P1-3 | **决策 D**：`agent/application/` → `app/application/` | 决策 D |
| P1-4 | **决策 C**：`agent/skills/` → `app/skills/` | 决策 C |
| P1-5 | **决策 B**：业务根文件归位（advisor、report、skill_coverage、intent_router 等；graph/state/ports 绑定 runtime 后续任务） | 决策 B |
| P1-6 | **决策 E**：移除 LangGraph，改纯 Python ReAct 循环 | 决策 E |
| P1-7 | 合并 `stream_chat_*` 切片群 | diagnosis 7 |
| P1-8 | `review_issue_chain_*` / `repair_pack_*` 切片收回 | diagnosis 2.2（✅ 子包归位完成；继续单文件收回需先满足 500 行预算） |

> 2026-07-17 同步：diagnosis 剩余 P1-7/P1-8 已完成旧壳删除，
> `context/selectors/` 轻量 selector 真实入口为 `selectors/core.py` 或包级
> `app.context.selectors`，`manage-crop-cycle/scripts/` 小 operation 真实入口为
> `scripts/main.py`。
> `memory.py`、`planting.py`、`update_cycle.py`、`update_stage.py` 因职责独立与
> 单文件 500 行预算继续保留；LangGraph E 与 P2 document_repository 仍未标记完成。

### 6.3 阶段 P2：子系统拆分（第 4-5 周）

| 编号 | 动作 | 来源 |
| --- | --- | --- |
| P2-1 | **决策 A 前置**：抽 `judge_service` / `repository_selector` 到共享层 | 决策 A |
| P2-2 | **决策 A**：`evaluation/` 与 `data_flywheel/` 迁入 `platforms/` | 决策 A |
| P2-3 | 确认生产配置、settings 默认、测试路径、回滚策略和 Mongo 迁移状态后，砍掉 `document_repository_*` 12 个未用 backend 类 | diagnosis 9-#2 |
| P2-4 | `infra/online_document_common.py` 3 Protocol 同步处理 | diagnosis 9-#5 |
| P2-5 | `services/` 21 个 *_service.py 评估合并 | diagnosis 3 |
| P2-6 | `tests/` 根目录 78 个 test_*.py 下沉 | diagnosis 5 |

### 6.4 阶段 P3：长期治理（持续）

| 编号 | 动作 | 来源 |
| --- | --- | --- |
| P3-1 | 巨石文件拆分（tool_executor 1517、classifier 1233、nodes 1049） | diagnosis 1 |
| P3-2 | 引入"新增 Protocol/ABC 必须列出 ≥2 实现"CI sensor | diagnosis 9 |
| P3-3 | 引入"新增 backend 实现必须证明使用"CI sensor | diagnosis 9-#2 |
| P3-4 | 日志轮转配置补全 | diagnosis 6 |

### 6.5 阶段间依赖

```text
P0 ──→ P1 ──→ P2 ──→ P3
        │
        └─→ P1-3（application 拆出）必须先于 P1-6（移除 LangGraph）
        └─→ P2-1（共享层）必须先于 P2-2（platforms 迁移）
        └─→ P2-3（确认后删 12 个 backend 类）必须先于 P2-2 中 data_flywheel 整体迁移
```

---

## 7. 风险与权衡

### 7.1 主要风险

| 风险 | 等级 | 缓解措施 |
| --- | --- | --- |
| 大量 import 搜替换可能漏改 | 中 | 每步 PR 后跑 CI + `check-layer-deps.sh` + `harness-check.sh` |
| 旧 import / 动态 patch 路径一次性迁移导致测试大面积失败 | 中 | C0/D0 先建兼容别名，再分批迁移生产代码与测试，最后删除旧路径 |
| LangGraph 移除后流式行为不一致 | 中 | E1-E3 单独 PR，必须用真实对话回归测试 |
| `document_repository_*` 删除破坏测试默认或回滚路径 | 中 | 删除前同时确认 `backend/config.yaml`、settings 默认值、Mongo 迁移 OpenSpec 状态和回滚策略 |
| `application/` 与 `agent/` 边界未严格执行 | 中 | 写入 boundaries.md 并加 sensor（P3-2） |
| `platforms/` 迁移打破 evaluation ↔ data_flywheel 依赖 | 中 | A1-A3 前置必须先做且单独验证 |
| 业务方对 services/ 合并有异议 | 低 | P2-5 标记为待评审，可暂缓 |

### 7.2 回滚策略

- 每个迁移步骤一个独立 PR / commit
- 每步可通过 `git revert` 单独回滚
- 关键步骤（决策 E 移除 LangGraph）保留旧实现 1 个版本周期，验证后再彻底删除

### 7.3 不在本次范围内

- 拆分独立部署的服务（如 evaluation-as-a-service）
- 数据库 schema 变更
- API 契约变更
- 前端 admin-web 调整

---

## 8. 与现有文档的关系

| 文档 | 关系 | 同步动作 |
| --- | --- | --- |
| [backend-bloat-diagnosis.md](./2026-07-12-backend-bloat-diagnosis.md) | 诊断与整改追踪（动态） | 本 spec 的 5 个决策追加到该文档的"整改计划追踪"章节，编号 P0~P3 |
| [agent-module-remediation.md](./2026-07-12-agent-module-remediation.md) | agent 模块专项整改 | 与本 spec 决策 B 重叠部分以本 spec 为准（更新、更全） |
| [../architecture/boundaries.md](../architecture/boundaries.md) | 依赖方向定义 | P2 完成后更新：新增 `application/`、`skills/`、`platforms/` 的边界规则 |
| [../architecture/overview.md](../architecture/overview.md) | 系统总览 | P2 完成后更新"当前落地目录"小节 |
| [../architecture/evolution-roadmap.md](../architecture/evolution-roadmap.md) | 演进路线 | P3 完成后追加"2026-07 目录重设计完成"里程碑 |

---

## 9. 整改追踪

> 本 spec 的 5 个决策拆为 23 个迁移步骤。每个步骤完成后更新对应行的"状态"列。
> 与 [backend-bloat-diagnosis.md 整改计划追踪](./2026-07-12-backend-bloat-diagnosis.md#整改计划追踪)
> 双向同步：本表专注"决策级"，那张表覆盖"诊断发现级"。

### 决策 A：拆分 platforms/

| 步骤 | 动作 | 状态 | commit |
| --- | --- | --- | --- |
| A1 | 抽 `judge_service` 到 `platforms/shared/` | ✅ | PR #16 |
| A2 | 抽 `repository_selector`；修 infra 反向调用 | ✅ | PR #16 |
| A3 | 评估 `rule_engine` 是否共享 | ✅ 暂不迁移 | PR #16 |
| A4 | `evaluation/` 迁入 `platforms/` | ✅ | PR #17 |
| A5 | `data_flywheel/` 迁入 `platforms/` | ✅ | PR #18 |
| A6 | 更新 boundaries.md | ✅ | PR #18 |
| A7 | `review_issue_chain_*` / `repair_pack_*` 归位到 DataFlywheel 子包并保留 root 兼容入口 | ✅ 本 PR | 本轮 PR |

### 决策 B：agent/ 瘦身

| 步骤 | 动作 | 状态 | commit |
| --- | --- | --- | --- |
| B1 | 删 `agent/planner/` | ✅ | 本工作树待提交 |
| B2 | 评估并迁移/收拢 `agent/planning/` | ✅ | 本工作树待提交 |
| B3 | 业务根文件归位 | ✅ 业务根文件完成；runtime 根文件待 P1-6/P1-runtime | 已完成 routing/core 子集：`intent_router`、`tool_selector`、`tool_selection_rules`、`llm`、`assistant_roles`；本轮完成 `advisor`、`report`、`skill_coverage` 阶段性归位并保留旧路径兼容入口 |

### 决策 C：skills/ 拆出

| 步骤 | 动作 | 状态 | commit |
| --- | --- | --- | --- |
| C0 | 建立旧 agent skills 路径兼容别名 | ✅ 历史 PR 已处理 | 迁移期护栏，已在 C4 退出 |
| C1 | `git mv app/agent/skills app/skills` | ✅ 本 PR 已处理 | refactor: 迁移 skills 到顶层包 |
| C2 | 全局搜替换 import | ✅ 本 PR 已处理 | 生产代码与关键测试改为 `app.skills` |
| C3 | 核对 registry 加载机制 | ✅ 本 PR 已处理 | `SkillManager` 扫描 `app.skills`；registry YAML 跟随迁移到 `app/skills/registry`；`agent/executor` 仍仅依赖 registry/metadata/tool manager，不直接 import 具体业务 skill |
| C4 | 移除旧路径兼容层 | ✅ 本轮完成 | 删除旧 agent skills 兼容入口，测试改为新路径护栏 |

### 决策 D：新建 application/

| 步骤 | 动作 | 状态 | commit |
| --- | --- | --- | --- |
| D0 | 建立旧 agent application 路径兼容别名 | ✅ 历史 PR 已处理 | 迁移期护栏，已在 D4 退出 |
| D1 | `git mv app/agent/application app/application` | ✅ 本轮已处理 | refactor: 迁移 application 到顶层包 |
| D2 | 全局搜替换 import | ✅ 本轮已处理 | 生产代码与普通行为测试改为 `app.application` 真实子包路径 |
| D3 | 内部重组（chat/session/advice 子包归位；stream 进一步合并待后续） | ✅ 子包归位完成 | 本轮 PR |
| D4 | 移除旧路径兼容层 | ✅ 本轮完成 | 删除旧 agent application 与旧 application 根 use case 兼容入口，旧兼容测试退场 |

### 决策 E：移除 LangGraph

| 步骤 | 动作 | 状态 | commit |
| --- | --- | --- | --- |
| E1 | 实现 `loop.py` 等价 ReAct 循环 | ⏳ | — |
| E2 | 替换 graph_factory 调用方 | ⏳ | — |
| E3 | 核对流式输出与 trace 重放 | ⏳ | — |
| E4 | 删除 langgraph 依赖 | ⏳ | — |

### 状态图例

| 图例 | 含义 |
| --- | --- |
| ⏳ | 待启动 |
| 🚧 | 进行中（附 WIP commit） |
| ✅ | 完成（附 commit hash） |
| ❌ | 阻塞（附原因） |
| ⚠️ | 待业务/评审确认 |

---

## 10. 文档状态

- **2026-07-14**：初版。整合 5 个设计决策（platforms 拆分、agent 瘦身、skills 拆出、application 新建、移除 LangGraph），
  与 [backend-bloat-diagnosis.md](./2026-07-12-backend-bloat-diagnosis.md) 互补。
- 本 spec 是**目标架构与迁移路径**的单一来源；诊断数字与具体整改追踪以 diagnosis 文档为准。
- 后续每次完成一个迁移步骤，同步更新第 9 章对应行的"状态"与"commit"列。
