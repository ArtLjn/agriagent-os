---
last_updated: 2026-06-03
status: active
---

# 系统架构

## 当前架构

当前后端是 FastAPI + SQLAlchemy + LangGraph + Skill 工具调用体系，目录仍以技术层为主：

```text
backend/app/
├── api/          # HTTP 路由、请求校验、依赖注入
├── services/     # 业务服务和应用编排
├── models/       # SQLAlchemy 数据模型
├── schemas/      # Pydantic 输入输出模型
├── agent/        # LangGraph、Prompt、Skill、Guardrails
├── infra/        # trace、限流、缓存、pending action 等适配
├── core/         # 配置、数据库、安全基础能力
└── simulation/   # Agent 仿真和回归基础
```

现阶段允许兼容旧入口，但新增能力必须向目标架构迁移，避免继续把 Agent、Prompt、Context、Memory 职责堆入 `api/agent.py`、`agent/graph.py` 或通用 service。

## 当前落地目录

```text
backend/app/
├── bootstrap/       # 应用启动、路由注册、lifespan、middleware
├── core/            # config、database、logger、安全 primitives
├── modules/         # 已迁移业务能力模块
│   ├── auth/
│   └── farm/
├── agent/           # Agent 平台主域
├── prompt/          # Prompt 工程：版本、片段、渲染、快照
├── context/         # Context 工程：选择、预算、压缩、缓存
├── memory/          # 短时记忆、长时记忆、检索、沉淀
├── evaluation/      # 回放、评测、指标、报告、基线
├── observability/   # trace、token、latency、tool call 监控
└── infra/           # 外部 provider、cache、queue、vector store adapter
```

`modules/crop`、`modules/cycle`、`modules/ledger`、`modules/weather`、`modules/conversation`、`modules/feedback`、`modules/admin` 以及平台级 `skills/` 属于后续迁移目标。当前不保留只有 `__init__.py` 的空壳目录，避免目录树和真实职责脱节。

## Agent 平台边界

Agent 平台由 `agent/`、`prompt/`、`context/`、`memory/`、`evaluation/`、`observability/` 共同组成；Skill 实现当前仍在 `agent/skills/`，后续若拆为平台级 `skills/`，必须同步迁移注册、权限、schema 和执行适配，而不是先建空目录。

- `agent/application/` 承接聊天、流式聊天、每日建议和报告生成 use case，API 只调用 use case。
- `agent/runtime/` 只负责图执行、节点协议、状态流转和 runtime 错误，不保存 Prompt、Context 或 Memory 的平台实现。
- `agent/planner/` 负责意图识别、任务规划和工具候选选择。
- `agent/executor/` 负责 Skill 调用、并行执行、权限分级、参数校验和写操作确认。
- `agent/response/` 负责结构化回复、流式事件和输出格式约束。
- `prompt/` 负责 Prompt 版本治理、片段组合、渲染和快照测试；真实片段文件仍在 `backend/prompts/snippets/`，不在 `app/prompt/snippets/` 放空包。
- `context/` 负责 ContextBundle、ContextBlock、selector、token 预算、压缩和缓存。
- `memory/` 负责短时记忆、长时记忆、检索和 observation event；Agent 只能通过 Memory Service 接口访问。
- `evaluation/` 负责 Agent 回放、Prompt 回归、Context 质量、Skill 调用质量和结构化报告。
- `observability/` 负责平台级 trace、token、延迟、tool call、memory observe 和 evaluation capture 事件。

## 标准请求生命周期

```text
认证与农场上下文
  → Agent application use case
  → Planner 意图和任务规划
  → Context Builder 构建 ContextBundle
  → Prompt Composer 渲染 Prompt
  → Runtime 执行图和节点
  → Executor 调用 Skill
  → Response Formatter 输出回复
  → Memory observation event
  → Trace 与 Evaluation capture
```

## 迁移阶段

1. 架构文档与边界固化：更新文档和约束脚本，先让规则可见、可检查。
2. Auth 模块化：创建 `modules/auth/`，集中 token、password、dependencies、permissions、errors。
3. Bootstrap 与 API 瘦身：创建 `bootstrap/`，让 `main.py` 和 API 路由只保留入口职责。
4. Agent Runtime 拆分：把 `agent/graph.py` 拆为 graph factory、state、nodes、tool executor、stream events。
5. Prompt 工程化：创建 `prompt/`，管理 registry、renderer、composer、versions、snippets、snapshots。
6. Context 工程化：创建 `context/`，定义 ContextBundle、selectors、budget、compressors、preload、cache。
7. Memory 骨架：创建 `memory/`，提供 build_context、observe_interaction、search 接口。
8. Evaluation 与 Observability：创建 `evaluation/` 和 `observability/`，把回放、指标、trace 扩展为平台门禁。

## 前端分层

```text
admin-web/src/
├── api/          # 不依赖 components、layouts、pages
├── components/   # 可依赖 api
├── layouts/      # 不依赖 api、components、pages
├── pages/        # 可依赖 api、components
└── main.ts       # 入口
```

## 核心约定

- 横切关注点（auth/log/telemetry）通过依赖注入，不被业务层直接 import。
- API 版本统一 v1，路径前缀 `/api/v1/`。
- API 层不承载 memory、prompt、context 业务逻辑。
- Agent Runtime 不承载 Prompt、Context、Memory 的存储实现或平台治理实现。
- 数据库迁移只用 alembic，禁止手动改表。
- 数据库统一使用 MySQL 8.x，连接串需包含 `charset=utf8mb4`。
