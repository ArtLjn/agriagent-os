## Context

当前后端是 FastAPI + SQLAlchemy + LangGraph + Skill 工具调用体系。经过多轮迭代后，后端已经有用户认证、农场业务、天气、账务、对话、Agent、Prompt、Trace、仿真测试等能力，但架构仍以技术层目录为主：

```text
backend/app/
├── api/
├── services/
├── models/
├── schemas/
├── agent/
├── infra/
├── core/
└── simulation/
```

这种结构在早期足够直接，但对成熟 Agent 系统不再够用。当前主要问题：

- `agent/graph.py` 过大，承载图构建、节点执行、上下文读取、工具执行、quota、trace、缓存等多种职责。
- `api/agent.py` 混入 SSE、trace 查询、消息保存、pending action 编排，API 层不够薄。
- Auth、Farm 上下文、管理员权限散落在 `api/deps.py`、`core/security.py`、`services/auth_service.py` 中，安全边界不集中。
- Prompt 仍偏模板管理，缺少版本治理、快照测试、回放验证和变更影响控制。
- Context 构建逻辑分散在 Agent、service、prompt composer 和缓存中，缺少统一的 token 预算和上下文选择策略。
- Memory 未来会涉及短时、长时、检索、沉淀，如果直接放进 Agent 或 service，会扩大现有耦合。
- Evaluation 已有 simulation 基础，但还不是 Agent 平台的回归门禁。

本设计目标是建立长期可演进的 Agent Platform 架构地基，并把大改拆成可验证的小阶段。

## Goals / Non-Goals

**Goals:**

- 建立成熟 Agent 系统的目标目录、依赖方向和模块边界。
- 将 Auth 设计为独立安全边界，承载 token、密码、权限、用户依赖。
- 将 Agent 拆为 application、runtime、planner、executor、response、guardrails、sessions 等子域。
- 将 Prompt 工程、Context 工程、Memory、Evaluation、Observability 从 Agent 内部分离成独立能力。
- 为短时记忆、长时记忆、语义检索、Prompt 版本治理、工具权限和回放评测预留稳定入口。
- 保持外部 API 行为兼容，按阶段迁移，降低与其他进行中 change 的冲突。

**Non-Goals:**

- 本变更不一次性重写所有后端代码。
- 本变更不立即引入向量数据库。
- 本变更不改变现有移动端或管理端 API 协议。
- 本变更不替换 LangGraph 或 Skillify。
- 本变更不把所有业务都改成完整 DDD；只对复杂边界做模块化。

## Decisions

### D1: 采用“业务模块 + Agent 平台域 + 共享基础设施”的目标结构

长期目标结构：

```text
backend/app/
├── bootstrap/              # 应用启动、路由注册、lifespan、middleware
├── core/                   # config、database、logger、security primitives
├── shared/                 # 通用 schema、错误响应、分页、时间、事务工具
├── modules/                # 业务能力模块
│   ├── auth/
│   ├── farm/
│   ├── crop/
│   ├── cycle/
│   ├── ledger/
│   ├── weather/
│   ├── conversation/
│   ├── feedback/
│   └── admin/
├── agent/                  # Agent 平台主域
├── prompt/                 # Prompt 工程
├── context/                # Context 工程
├── memory/                 # 短时/长时记忆
├── skills/                 # 工具注册、权限、schema、执行适配
├── evaluation/             # 回放、评测、回归报告
├── observability/          # trace、token、latency、tool call 监控
└── infra/                  # 外部 provider、cache、queue、vector store adapter
```

备选方案：

- 继续维持技术分层：短期改动少，但会继续让 Agent、Auth、Context 横跨多个目录。
- 全量 DDD：边界更纯，但迁移成本高，不适合当前已有大量功能的项目。

选择理由：该结构保留现有 FastAPI + SQLAlchemy 模式，同时给 Agent 平台单独的演进空间。

本阶段只创建已经承载真实职责的目录。未迁移业务模块（如 crop、cycle、ledger、weather、conversation、feedback、admin）、平台级 skills、shared 以及 prompt 下的 versions/snippets/snapshots 不使用空目录占位；等对应 router/service/dependencies/ports、注册策略或快照资产真实落地时再创建。

### D2: Auth 独立为安全模块，Farm 上下文不放在 Auth 内

Auth 目标结构：

```text
modules/auth/
├── router.py
├── schemas.py
├── service.py
├── dependencies.py
├── password.py
├── tokens.py
├── permissions.py
└── errors.py
```

`get_current_user`、`require_admin` 属于 Auth。`get_current_farm` 属于 Farm 上下文，应放在 `modules/farm/dependencies.py`，通过 `auth.dependencies.get_current_user` 组合。

选择理由：Auth 负责“谁在请求”和“是否有权限”，Farm 负责“当前用户对应哪个农场”。注册时创建默认农场也应通过 Farm 模块接口完成，而不是 Auth 直接操作 Farm 模型。

### D3: Agent Runtime 与 Agent Application 分离

Agent 目标结构：

```text
agent/
├── application/
│   ├── chat_use_case.py
│   ├── stream_chat_use_case.py
│   ├── daily_advice_use_case.py
│   └── report_use_case.py
├── runtime/
│   ├── graph_factory.py
│   ├── state.py
│   ├── nodes.py
│   ├── tool_executor.py
│   ├── stream_events.py
│   └── errors.py
├── planner/
├── executor/
├── response/
├── guardrails/
├── sessions/
└── ports.py
```

API 层只调用 use case。Runtime 只负责图执行和节点协议。Planner 负责意图、任务拆解和工具候选。Executor 负责工具调用、权限、并行、写操作确认。Response 负责结构化回复和流式事件。

选择理由：未来要扩展 planner、多步骤任务、工具权限、写操作确认和 memory 注入时，不再继续膨胀 `graph.py`。

### D4: Prompt 与 Context 分离

Prompt 工程只负责“如何表达给模型”。长期目标结构：

```text
prompt/
├── registry.py
├── renderer.py
├── composer.py
├── versions/
├── snippets/
├── policy.py
└── snapshots/
```

当前阶段中，Prompt 版本治理和片段治理由 `prompt/registry.py`、`prompt/composer.py`、`prompt/replay.py` 以及 `backend/prompts/snippets/` 承载，不创建空的 `app/prompt/versions`、`app/prompt/snippets` 或 `app/prompt/snapshots` 包。

Context 工程负责“给模型什么信息、给多少、按什么顺序给”：

```text
context/
├── builder.py
├── budget.py
├── models.py
├── selectors/
├── compressors/
├── preload.py
└── cache.py
```

选择理由：Prompt 变化和 Context 变化的风险不同。Prompt 需要版本、快照、回放验证；Context 需要 token 预算、缓存、压缩和召回质量指标。

### D5: Memory 是独立模块，不内嵌到 Agent

Memory 目标结构：

```text
memory/
├── short_term/
├── long_term/
├── retrieval/
├── consolidation/
├── models.py
├── schemas.py
├── service.py
└── ports.py
```

Agent 通过 `MemoryService` 获取上下文和写入观察事件：

```python
class MemoryService:
    async def build_context(user_id: str, farm_id: int, session_id: str | None) -> MemoryContext:
        ...

    async def observe_interaction(event: MemoryEvent) -> None:
        ...

    async def search(query: str, farm_id: int, limit: int = 5) -> list[MemoryHit]:
        ...
```

初期只实现接口、短时会话摘要和观察事件。长时事实抽取、向量检索和异步沉淀在后续 change 中展开。

选择理由：Memory 会同时服务 Agent、Context、Evaluation 和未来用户画像，不应成为 Agent Runtime 的内部细节。

### D6: Evaluation 成为 Agent 平台门禁

目标结构：

```text
evaluation/
├── cases/
├── runners/
├── replay/
├── metrics/
├── reports/
└── baselines/
```

评测维度包括：

- 回复格式正确率
- Skill 调用准确率
- 写操作确认命中率
- 上下文命中率
- Memory 召回质量
- Prompt 版本回归差异
- token 成本和响应延迟

选择理由：成熟 Agent 系统的核心不是“能回答”，而是每次改 prompt、context、tool、memory 后能知道有没有退化。

### D7: 分阶段迁移，不做一次性大重构

阶段顺序：

1. 架构文档和 OpenSpec 固化。
2. Auth 模块化。
3. `main.py` 和 API 层瘦身。
4. Agent Runtime 拆分。
5. Prompt 工程化。
6. Context 工程化。
7. Memory 骨架。
8. Evaluation 门禁。

选择理由：当前已有 MySQL 迁移、用户额度、每日建议等进行中 change。阶段化能减少冲突，也能每一步跑测试。

## Risks / Trade-offs

- [目录迁移带来 import churn] → 每阶段只迁移一个边界，保留兼容 wrapper，完成后再删除旧入口。
- [Auth 改动影响所有受保护 API] → 先补充 auth/deps 测试，再迁移依赖路径。
- [Agent Runtime 拆分可能改变流式行为] → 对 `chat` 和 `chat/stream` 建回归测试，固定 SSE 事件格式。
- [Prompt 和 Context 分离后调用链变长] → 用 `ContextBundle` 和 `PromptInput` 作为清晰数据结构，避免传 dict 漫游。
- [Memory 过早复杂化] → 初期只做接口、短时摘要和 observation，向量检索另开 change。
- [Evaluation 建设成本高] → 先复用现有 simulation，逐步升级为平台门禁。

## Migration Plan

1. 创建 `modules/auth`，迁移 token、password、dependencies，保留旧 `api/deps.py` re-export，确保外部 import 暂不破。
2. 创建 `bootstrap`，迁移路由注册、lifespan、middleware，保持 `main.py` 作为薄入口。
3. 创建 `agent/application`，把 `api/agent.py` 中的 SSE、消息保存、trace skill 查询下沉到 use case。
4. 拆分 `agent/runtime`，把 `graph.py` 分解为 graph factory、nodes、tool executor、stream events。
5. 创建 `prompt` 包，迁移 registry、renderer、composer，并建立 snapshot 测试。
6. 创建 `context` 包，定义 `ContextBlock`、`ContextBundle`、token budget 和 selectors。
7. 创建 `memory` 包，接入 short-term context 和 observe interaction 事件。
8. 创建 `evaluation` 包，复用 simulation case，增加 prompt/context/skill 回归报告。

Rollback 策略：每个阶段保留旧 import wrapper 和旧 API 行为；若失败，回退该阶段迁移提交，不影响其他阶段。

## Open Questions

- 长时记忆的第一版存储继续使用 MySQL 表，还是在 MySQL 稳定后引入独立向量库。
- Skill 是否从 `agent/skills` 独立迁移为顶层 `skills/`，还是先保留在 Agent 内部。
- Prompt 版本切换是否需要管理端 UI，还是先通过配置文件和热加载实现。
- Evaluation 是否接入 CI 七道门，还是先作为手动回归命令。
