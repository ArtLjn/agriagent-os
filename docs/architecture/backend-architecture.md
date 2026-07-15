---
last_updated: 2026-06-08
status: active
---

# 后端系统架构

> 基于 `backend/app` 当前代码扫描更新。本文只描述真实落地结构；历史兼容入口见 [compatibility-entries.md](/Users/ljn/Documents/demo/explore/docs/architecture/compatibility-entries.md)。

## 1. 当前分层

后端是 FastAPI + SQLAlchemy + LangGraph + Skillify Skill 体系。入口已从单文件启动迁移到 `app/bootstrap/`，Agent 平台也已拆出 application、runtime、planner、executor、response、context、memory、evaluation 等子域。

```mermaid
flowchart TB
    Client["移动端 / Admin Web"]
    Bootstrap["bootstrap\n应用工厂、路由、中间件、异常、lifespan"]
    API["api\nHTTP 路由和依赖注入"]
    AppUseCase["agent/application\n聊天、流式、每日建议、报告、历史"]
    Service["services / modules\n业务服务、认证、天气、配额"]
    AgentPlatform["agent 平台\nadvisor、runtime、planner、executor、skills"]
    ContextMemory["context / memory\n上下文选择、预算、短时/长时记忆"]
    Prompt["prompt + prompts/\nPrompt 注册、组合、渲染、模板文件"]
    Infra["infra / core\n数据库、配置、日志、限流、trace、熔断"]
    Data["MySQL 8.x\nSQLAlchemy Models + Alembic"]
    External["外部服务\nLLM Provider、天气 Provider"]

    Client --> Bootstrap --> API
    API --> AppUseCase
    API --> Service
    AppUseCase --> Service
    AppUseCase --> AgentPlatform
    AgentPlatform --> ContextMemory
    AgentPlatform --> Prompt
    AgentPlatform --> Infra
    Service --> Infra
    Infra --> Data
    Infra --> External
```

## 2. 目录职责

| 目录 | 当前职责 |
| --- | --- |
| `app/main.py` | 仅创建 FastAPI app；本地运行时读取 `settings.server` 启动 uvicorn。 |
| `app/bootstrap/` | 应用工厂、路由注册、中间件、异常处理、lifespan。 |
| `app/api/` | HTTP 入口、参数校验、FastAPI Depends；Agent 路由已主要调用 application use case，智能填写通过 `api/smart_fill.py` 暴露统一场景入口。 |
| `app/modules/auth`、`app/modules/farm` | 已迁移的模块化认证和农场依赖能力。 |
| `app/services/` | 迁移期业务服务：作物、周期、日志、成本、债务、天气、会话、报告、配额。 |
| `app/agent/application/` | Agent 应用用例：聊天、SSE、每日建议、报告、历史、上下文失效。 |
| `app/agent/runtime/` | LangGraph 图工厂、节点、消息压缩、工具执行、最终 prompt 预算、流式事件。 |
| `app/agent/executor/` | Tool call 执行计划和并行执行适配。 |
| `app/agent/skills/` | Skillify Skill 实现，目前仍位于 Agent 域下。 |
| `app/context/` | ContextBundle、selector、token budget、压缩、缓存、预加载和失效。 |
| `app/memory/` | 短时记忆、长时记忆接口、检索空实现、observation event。 |
| `app/prompt/` 与 `backend/prompts/` | Prompt registry/composer/renderer/replay 代码与 Jinja2 模板文件。 |
| `app/infra/` | trace、pending action、limiter、skill cache、circuit breaker、兼容 settings/database/json_repair。 |
| `app/core/` | 配置、数据库、日志、安全、日期上下文、LLM client manager。 |
| `app/evaluation/`、`app/simulation/`、`app/observability/` | 回放评测、仿真测试、平台观测事件骨架。 |

## 3. Agent 请求链路

```mermaid
sequenceDiagram
    participant C as 客户端
    participant API as api/agent.py
    participant UC as agent/application
    participant SVC as services/agent_service.py
    participant ADV as agent/advisor.py
    participant RT as agent/runtime
    participant CTX as context + memory
    participant LLM as LLM Provider
    participant SK as skills
    participant DB as 数据库

    C->>API: POST /agent/chat 或 /agent/chat/stream
    API->>UC: chat / stream_chat_events
    UC->>SVC: chat_with_agent / stream_chat_with_agent
    SVC->>DB: 保存用户消息并读取会话
    SVC->>ADV: invoke_advisor / stream_advisor
    ADV->>ADV: Guardrails + 问候/待确认意图处理
    ADV->>RT: LangGraph ainvoke / astream
    RT->>CTX: 构建 ContextBundle 和 MemoryContext
    RT->>LLM: 绑定筛选后的 Tools 调用模型
    LLM-->>RT: AIMessage 或 tool_calls
    RT->>SK: 并行执行 Skill
    SK->>DB: 按需读写业务数据
    RT-->>ADV: 最终回复
    ADV-->>SVC: 输出过滤后的文本
    SVC->>DB: 保存 AgentRecord / ConversationMessage
    UC->>UC: 提交 Memory observation
    UC-->>API: ChatResponse 或 SSE
```

## 4. Agent 平台拆分

```mermaid
flowchart LR
    Application["application\n用例编排"]
    Advisor["advisor.py\n兼容入口、Guardrails、pending action"]
    Planner["planner / tool_selector\n意图识别、候选工具"]
    Runtime["runtime\nLangGraph 节点、消息、预算、流事件"]
    Executor["executor / runtime.tool_executor\n并行工具执行"]
    Skills["skills\n只读查询 + 写操作确认"]
    Response["response\nSSE 与文本格式化"]
    Trace["infra.trace_collector\nprompt、context、skill、token 记录"]

    Application --> Advisor --> Runtime
    Runtime --> Planner
    Runtime --> Executor --> Skills
    Runtime --> Response
    Runtime --> Trace
    Skills --> Trace
```

当前 `app.agent.graph` 仍是 Runtime 兼容入口；Prompt 相关调用已迁移到 `app.prompt`。新增实现应优先进入 `agent/runtime`、`prompt/`、`context/`、`memory/` 对应边界。

## 5. Context、Prompt、Memory 链路

```mermaid
flowchart TB
    Request["ContextBuildRequest\nfarm_id、intent、tool_names、session_id"]
    Policy["ContextPolicy\n选择层和 token 上限"]
    Builder["ContextBuilder"]
    Selectors["selectors\nfarm、cycle、settings、ledger、weather、conversation、memory、retrieval"]
    Budget["TokenBudget\n裁剪和压缩"]
    Bundle["ContextBundle\n渲染 runtime_context"]
    Memory["MemoryService\nrecent messages、summary、pending、observation"]
    Composer["PromptComposer\nsnippet 组合"]
    Cache["PromptCache / FarmContextCache"]
    Runtime["Runtime LLM Node"]

    Request --> Policy --> Builder
    Builder --> Selectors --> Budget --> Bundle
    Memory --> Builder
    Bundle --> Runtime
    Cache --> Runtime
    Composer --> Runtime
```

设计边界：Runtime 可以消费 `ContextBundle` 和已构造好的 memory view，但不应直接实现 selector、memory store 或 prompt 版本治理。

## 5.1 智能填写统一入口

```mermaid
flowchart LR
    Client["移动端 / Admin Web"]
    SmartAPI["api/smart_fill.py\n/scenarios + /parse"]
    Registry["agent.application.smart_fill\n场景注册表"]
    Prompt["PromptComposer\ncost/crop/cycle parse"]
    LLM["LLM structured output\nJSON fallback"]
    Draft["表单草稿\n不直接落库"]
    Legacy["旧 parse 入口\n/costs /crops /cycles"]

    Client --> SmartAPI --> Registry --> Prompt --> LLM --> Draft
    Legacy --> Registry
```

智能填写统一为“自然语言 → 表单草稿”，当前注册 `ledger.record`、`crop.template`、`crop.cycle` 三个场景。场景注册项声明 prompt、输出 schema、上下文构建和业务校验；新增业务不再新增专属 parse 路由，优先扩展 `agent.application.smart_fill`。旧 `/costs/parse`、`/crops/templates/parse`、`/cycles/parse` 保留为兼容入口，内部转调统一服务并返回旧响应格式。

## 6. Skill 系统

```mermaid
flowchart TB
    Manager["SkillManager\n扫描 app/agent/skills"]
    Adapter["skills_to_langchain_tools\n转 StructuredTool"]
    Read["只读 Skill\nweather、farm-status、cost-summary、cost-analytics、crop-cycle、farm-logs、web_search"]
    Write["写操作 Skill\nmanage-cost、manage-crop-cycle、manage-crop-templates、log-farm-activity、settle-debt"]
    Pending["pending_actions\n确认、取消、修改、链式后续动作"]
    Cache["skill_cache\n只读缓存"]
    Services["services\n业务读写"]

    Manager --> Adapter
    Adapter --> Read
    Adapter --> Write
    Read --> Cache --> Services
    Write --> Pending --> Services
```

写操作不会直接静默落库，通常注册为 pending action，由用户确认后再执行。作物周期创建、日期调整和阶段推进统一由 `manage_crop_cycle` 承接；`update_crop_stage` 只作为 registry legacy alias 兼容旧名。

## 7. LLM 与天气外部依赖

```mermaid
flowchart LR
    Runtime["agent/runtime"]
    LLMFactory["agent/llm.py"]
    Manager["core/llm_client_manager.py\n角色路由、权重、API Key 轮换、熔断"]
    Providers["providers.json\n多 provider / model 配置"]
    LLM["OpenAI 兼容 LLM 服务"]

    WeatherAPI["api/weather.py 或 weather skill"]
    WeatherSvc["services/weather_service.py"]
    Strategy["services/weather/strategy.py\n缓存、故障切换、预警注入"]
    QWeather["QWeather"]
    OpenMeteo["Open-Meteo"]

    Runtime --> LLMFactory --> Manager --> Providers
    Manager --> LLM
    WeatherAPI --> WeatherSvc --> Strategy
    Strategy --> QWeather
    Strategy --> OpenMeteo
```

LLM 路由按 `role` 选择模型，支持 provider/model 级错误分类和指数退避。天气策略优先使用配置了密钥的 QWeather，失败或未配置时使用 Open-Meteo。

## 8. 数据域概览

```mermaid
erDiagram
    User ||--o{ Farm : owns
    User ||--o{ UserSetting : has
    Farm ||--o{ CropTemplate : defines
    CropTemplate ||--o{ GrowthStage : has
    CropTemplate ||--o{ CropCycle : instantiates
    Farm ||--o{ CropCycle : runs
    CropCycle ||--o{ CycleStage : has
    Farm ||--o{ FarmLog : records
    Farm ||--o{ CostCategory : groups
    CostCategory ||--o{ CostRecord : categorizes
    Farm ||--o{ CostRecord : tracks
    User ||--o{ Conversation : starts
    Farm ||--o{ Conversation : hosts
    Conversation ||--o{ ConversationMessage : contains
    Farm ||--o{ AgentRecord : stores
    User ||--o{ FeedbackRecord : writes
    Farm ||--o{ TokenDailyStats : consumes
    Farm ||--o{ TraceRecord : traces
    SimulationRun ||--o{ SimulationResultRecord : contains
```

主要 ORM 位于 `app/models/`：用户、农场、作物模板、生长阶段、种植周期、周期阶段、日志、成本、分类、会话、消息、Agent 记录、反馈、trace、token 统计、幂等键和仿真记录。

## 9. 迁移关注点

- `api/agent.py` 已经瘦身，但仍通过 `services.agent_service` 进入旧 `advisor.py` 兼容入口。
- `agent/runtime/llm_support.py` 当前会构建 runtime context bundle，后续可继续向 application 注入端口的方向收敛。
- `services/` 仍承担大量业务模块职责，后续可逐步迁移到 `modules/farm`、`modules/ledger`、`modules/weather`、`modules/conversation` 等真实模块。
- `app/agent/skills/` 当前是平台能力和业务写入的交汇点，新增 Skill 要明确只读/写操作权限、缓存策略和 pending action 行为。
- 架构图应保持分图维护；不要把 API、Agent、Skill、DB、外部服务全部塞进一张图。
