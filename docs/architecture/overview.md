---
last_updated: 2026-07-19
status: active
---

# 系统架构

## 当前架构

当前后端是 FastAPI + SQLAlchemy + Skill 工具调用体系。入口已迁移到 `app/bootstrap/`，业务能力按领域目录收敛到 `domains/`，Agent 平台由 `application/`、`agent/`、`skills/`、`prompt/`、`context/`、`memory/` 和 `platforms/*` 共同承载。旧技术层入口已下线，不再保留兼容空壳。

```text
backend/app/
├── bootstrap/       # 应用工厂、路由注册、中间件、异常、lifespan
├── domains/         # 用户、农场、种植、财务、天气、会话等业务领域
├── application/     # 聊天、会话、建议、报告等 use case 编排
├── agent/           # Agent runtime、planner、executor、response、guardrails
├── skills/          # Skill 实现、注册、权限、schema 和执行适配
├── prompt/          # Prompt 注册、组合、渲染、回放
├── context/         # ContextBundle、selector、预算、压缩、缓存
├── memory/          # 短时记忆、长时记忆接口、检索、observation
├── platforms/       # admin、data_flywheel、evaluation、simulation、shared
├── shared/          # 配置、数据库、日志、安全、时间、LLM、模型注册
├── infra/           # trace、限流、缓存、pending action、熔断等适配
├── observability/   # 平台观测事件
└── ops/             # 运维辅助能力
```

新增能力必须落到真实领域或平台边界，避免重新创建 `api/`、`models/`、`schemas/`、`services/`、`modules/`、`core/`、`simulation/` 等旧技术层目录，也避免把 Agent、Prompt、Context、Memory 职责堆入通用 service。

## 当前落地目录

```text
backend/app/
├── bootstrap/       # 应用启动、路由注册、lifespan、middleware
├── domains/         # 业务领域
│   ├── users/       # 认证、用户、设置、配额、后台用户管理
│   ├── farm/        # 农场、当前农场上下文、农场报告数据
│   ├── planting/    # 作物模板、种植周期、农事日志、用工
│   ├── finance/     # 成本、分类、债务
│   ├── weather/     # 天气服务、地点解析
│   └── conversation/# 会话、反馈、日报建议、Agent 记录
├── application/     # chat/session/advice 子包及报告、能力菜单等 use case
├── agent/           # Agent 平台主域
├── skills/          # 平台级 Skill 实现、注册、权限、schema 和执行适配
├── prompt/          # Prompt 工程：版本、片段、渲染、快照
├── context/         # Context 工程：选择、预算、压缩、缓存
├── memory/          # 短时记忆、长时记忆、检索、沉淀
├── platforms/       # 平台级能力与共享层
│   ├── admin/       # 后台配置、看板、trace、版本路由
│   ├── evaluation/  # 回放、评测、指标、报告、基线
│   ├── data_flywheel/ # 样本、标注、问题链、repair pack 闭环
│   │   ├── review_issue_chain/ # 问题链 inbox、详情、case draft、repair pack 入口
│   │   └── repair_pack/        # repair pack 候选、payload、链路导出与 README
│   ├── simulation/  # Agent 仿真和回归基础
│   └── shared/      # 跨 evaluation 与 data_flywheel 的共享能力
├── shared/          # config、database、logger、安全、模型注册、JSON/时间工具
├── observability/   # trace、token、latency、tool call 监控
├── infra/           # 外部 provider、cache、queue、vector store adapter
└── ops/             # 运维脚本和检查辅助
```

`platforms/data_flywheel` 已承接 Agent 数据飞轮的样本服务、问题链服务和 repair pack 闭环；`platforms/admin` 承接后台配置、看板、trace 和版本路由；`platforms/evaluation` 承接 Evaluation 真实代码；`platforms/simulation` 承接 Agent 仿真和回归基础；`platforms/shared` 当前包含 judge service 与 repository selector 的真实入口。旧技术层入口和仅有 `__init__.py` 的空壳目录不再作为架构占位，新增目录必须有真实职责和调用方。

更细的后端结构、请求链路和分图见 [backend-architecture.md](/Users/ljn/Documents/demo/explore/docs/architecture/backend-architecture.md)。
Agent 数据飞轮的工业级完成态、AI 预标注边界和分阶段闭环路线见 [agent-data-flywheel-industrial-roadmap.md](/Users/ljn/Documents/demo/explore/docs/architecture/agent-data-flywheel-industrial-roadmap.md)。
Data Flywheel 失败样本导出为 vibecoding repair pack 的闭环流程见 [data-flywheel-repair-pack-workflow.md](/Users/ljn/Documents/demo/explore/docs/architecture/data-flywheel-repair-pack-workflow.md)。

## 作物模板边界

作物模板属于 `domains/planting/` 边界：SQLAlchemy 模型在 `domains/planting/crop_models.py`，业务逻辑在 `domains/planting/crop_service.py`，HTTP 路由在 `domains/planting/crop_routes.py`。系统作物模板库使用 `CropTemplate.farm_id IS NULL` 表示平台预置模板；用户私有模板仍使用具体 `farm_id`。因此用户模板查询必须显式过滤 `farm_id = 当前农场`，系统模板查询必须显式过滤 `farm_id IS NULL`，避免系统模板泄漏到用户私有列表。

系统模板采用导入即副本模式：`POST /crops/templates/system/{id}/import` 会把系统模板及其生长阶段复制到当前农场，复制后用户可自由编辑，原系统模板保持只读。创建和导入路径统一调用 `crop_service.find_exact_duplicate`，用 name、variety 与规范化 stages 做精确查重，避免 API、前端和 Skill 出现不一致的重复模板判断。

## Agent 平台边界

Agent 平台由 `application/`、`agent/`、`skills/`、`prompt/`、`context/`、`memory/`、`platforms/evaluation/`、`observability/` 共同组成；Skill 实现、注册、权限、schema 和执行适配已整体迁移到平台级 `skills/`，业务 use case 已迁移到顶层 `application/`，其中聊天、会话、建议和报告分别归入 `application/chat/`、`application/session/`、`application/advice/`、`application/report.py`；旧 agent skills、旧 agent application、旧 application 根 use case、已归位的 agent 根兼容入口与旧 Evaluation 根包均已删除。

- `application/` 承接聊天、流式聊天、每日建议、会话历史和报告生成 use case，API 只调用 use case。
- `agent/runtime/` 只负责图执行、节点协议、状态流转和 runtime 错误，不保存 Prompt、Context 或 Memory 的平台实现。
- `agent/executor/` 负责 Skill 调用、并行执行、权限分级、参数校验和写操作确认。
- `agent/reflector/` 负责触发式反思控制、写操作风险检查、工具结果一致性检查和 reflection trace payload；Runtime/Executor 只调用反思服务，不内联策略规则。
- `agent/response/` 负责结构化回复、流式事件和输出格式约束。
- `prompt/` 负责 Prompt 版本治理、片段组合、渲染和快照测试；真实片段文件仍在 `backend/prompts/snippets/`，不在 `app/prompt/snippets/` 放空包。
- `context/` 负责 ContextBundle、ContextBlock、selector、token 预算、压缩和缓存。
- `memory/` 负责短时记忆、长时记忆、检索和 observation event；Agent 只能通过 Memory Service 接口访问。
- `platforms/evaluation/` 负责 Agent 回放、Prompt 回归、Context 质量、Skill 调用质量和结构化报告。
- `platforms/data_flywheel/` 负责样本采集、标注、问题链和 repair pack 闭环；问题链与 repair pack 真实代码分别位于 `review_issue_chain/`、`repair_pack/` 子包，旧 root 兼容薄壳已下线。
- `observability/` 负责平台级 trace、token、延迟、tool call、memory observe 和 evaluation capture 事件。
- `DataFlywheel` 是 Agent 平台的数据加工台：从真实会话、trace、event log 和仿真失败中整理样本，经过规则候选、LLM 预标注和人工确认后，输出 regression case、evaluation replay 和训练数据。

Context 工程边界：Agent 不直接拼接全量业务数据。Runtime 通过 `ContextPolicy -> ContextBuilder -> ContextBundle -> TokenBudget` 构建动态上下文；短时记忆由 Memory Service 提供 session 视图，并经 application 层适配进入 runtime；详细账务、天气、日志和作物数据由 tool 按需查询。

Memory 部署边界：当前部署不内置 RAG、向量数据库、embedding 模型或重排服务，长期记忆和检索只通过 `MemoryService` 端口预留扩展点。未配置外部 RAG/memory 服务时，`MemoryService.build_context()` 返回空长期记忆上下文，`MemoryService.search()` 返回空检索结果，Agent 请求继续按短时上下文、业务工具和 Prompt 正常执行。未来独立 RAG/memory 服务通过 `MemoryService.search()` 和 `MemoryService.build_context()` 接入，不在当前 2h4g 部署内耦合重型检索基础设施。

## 标准请求生命周期

```text
认证与农场上下文
  → Agent application use case
  → Service 保存会话并处理 pending action
  → Advisor 真实入口处理 Guardrails 和直接意图
  → Runtime 执行节点状态机
  → Planner/Tool Selector 筛选候选工具
  → Context Builder + Memory Service 构建 ContextBundle
  → Prompt Composer 渲染 system prompt
  → Executor 并行调用 Skill
  → Reflection 检查写入风险、工具结果和最终回复一致性
  → Response Formatter / SSE 输出回复
  → Memory observation event
  → Trace 与 Evaluation capture
```

## 架构治理状态

1. `app.api`、`app.models`、`app.schemas`、`app.services`、`app.modules`、`app.core`、`app.simulation` 旧入口已下线，生产代码不得重新创建这些目录或兼容 re-export 壳。
2. 新业务默认进入 `domains/*`；Agent 平台能力进入 `agent/`、`skills/`、`prompt/`、`context/`、`memory/`；后台、评测、数据飞轮、仿真等横向平台能力进入 `platforms/*`。
3. 默认不要直接在 `main` 分支改代码。开发任务使用 `codex/*` 分支或独立 worktree，提交后通过 GitHub PR 审核合并。
4. 目录级变更必须同步更新 `AGENTS.md`、本文件、`docs/architecture/boundaries.md`，必要时同步 `scripts/check-layer-deps.sh` 和复杂度预算脚本。
5. 不为了规避行数预算拆 20-50 行碎片文件。生产 Python 文件 ≤ 1000 行；500-1000 行为观察区间，按职责混杂度判断是否收束。

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
- 新增代码不直接落 `main`；PR 描述必须写清变更范围、验证结果和剩余风险。
- 数据库迁移只用 alembic，禁止手动改表。
- 数据库统一使用 MySQL 8.x，连接串需包含 `charset=utf8mb4`。
