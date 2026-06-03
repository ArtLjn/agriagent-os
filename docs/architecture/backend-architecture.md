# 后端系统架构详细文档

> 生成时间: 2026-05-30 | 基于 backend/ 完整代码分析

---

## 目录

1. [总体架构图](#1-总体架构图)
2. [分层依赖图](#2-分层依赖图)
3. [请求流转图](#3-请求流转图)
4. [Agent 内部架构图](#4-agent-内部架构图)
5. [Skill 系统架构图](#5-skill-系统架构图)
6. [LLM 多 Provider 路由图](#6-llm-多-provider-路由图)
7. [天气双 Provider 架构图](#7-天气双-provider-架构图)
8. [数据模型 ER 图](#8-数据模型-er-图)
9. [模块职责清单](#9-模块职责清单)

---

## 1. 总体架构图

```mermaid
flowchart TB
    subgraph 客户端
        Mobile["📱 FarmManager Mobile<br/>(React Native + TS)"]
        Admin["🖥️ Admin Web<br/>(React + Vite)"]
    end

    subgraph "FastAPI 应用 (app/)"
        direction TB
        subgraph "API 层 (app/api/)"
            Auth["/auth<br/>认证路由"]
            AgentAPI["/agent<br/>AI 对话路由"]
            CropAPI["/crops<br/>作物模板路由"]
            CycleAPI["/cycles<br/>种植周期路由"]
            CostAPI["/costs<br/>记账路由"]
            WeatherAPI["/weather<br/>天气路由"]
            OtherAPI["/logs /debts<br/>/feedback /user-settings<br/>/admin"]
            Deps["deps.py<br/>DI: get_db<br/>get_current_user<br/>get_current_farm<br/>require_admin"]
        end

        subgraph "Agent 系统 (app/agent/)"
            Advisor["advisor.py<br/>Agent 入口"]
            Graph["graph.py<br/>LangGraph 状态机"]
            ToolSelector["tool_selector.py<br/>三层工具过滤"]
            Guardrails["guardrails.py<br/>输入/输出安全"]
            PromptReg["prompt_registry.py<br/>模板注册中心"]
            PromptRender["prompt_renderer.py<br/>Jinja2 渲染"]
            PromptComposer["prompt_composer.py<br/>snippet 组合"]
        end

        subgraph "服务层 (app/services/)"
            AgentSvc["agent_service.py"]
            AuthSvc["auth_service.py"]
            ConvSvc["conversation_service.py"]
            CostSvc["cost_service.py"]
            CropSvc["crop_service.py"]
            CycleSvc["cycle_service.py"]
            FarmCtx["farm_context_service.py"]
            WeatherSvc["weather_service.py"]
        end

        subgraph "基础设施 (app/infra/)"
            Limiter["limiter.py<br/>SlowAPI 限流"]
            CB["circuit_breaker.py<br/>三态熔断器"]
            Pending["pending_actions.py<br/>写操作确认"]
            Trace["trace_collector.py<br/>异步 Trace"]
            SkillCache["skill_cache.py<br/>TTL 缓存"]
        end
    end

    subgraph "Skill 系统 (app/agent/skills/)"
        S1["get_weather_forecast"]
        S2["get_farm_status"]
        S3["get_cost_summary"]
        S4["get_cost_analytics"]
        S5["create_cost_record"]
        S6["get_crop_cycle_info"]
        S7["create_crop_cycle"]
        S8["create_crop_template"]
        S9["get_recent_farm_logs"]
        S10["log_farm_activity"]
        S11["update_crop_stage"]
        S12["settle_debt"]
    end

    subgraph "核心层 (app/core/)"
        Config["settings/<br/>pydantic-settings"]
        DB["database.py<br/>MySQL 连接池"]
        Security["security.py<br/>JWT + bcrypt"]
        Logger["logger.py<br/>结构化日志"]
        LLMMgr["llm_client_manager.py<br/>多 Provider 路由"]
    end

    subgraph "外部服务"
        LLMProv["LLM Providers<br/>Ollama / NVIDIA / DashScope"]
        QWeather["和风天气 API"]
        OpenMeteo["Open-Meteo API"]
    end

    subgraph "数据层"
        MySQL[("MySQL 8.x<br/>farm_manager<br/>20 张表")]
        PromptFiles["prompts/<br/>snippets/ + templates<br/>config.yaml"]
        ProvidersJSON["providers.json<br/>LLM 路由配置"]
    end

    Mobile --> Auth & AgentAPI & CropAPI & CycleAPI & CostAPI & WeatherAPI & OtherAPI
    Admin --> OtherAPI
    Auth & AgentAPI & CropAPI & CycleAPI & CostAPI & WeatherAPI & OtherAPI --> Deps
    Deps --> Config & DB & Security

    AgentAPI --> Advisor
    Advisor --> Graph
    Graph --> ToolSelector & Guardrails & Composer
    Composer --> PromptReg & PromptRender
    PromptRender --> PromptFiles
    ToolSelector --> S1 & S2 & S3 & S4 & S5 & S6 & S7 & S8 & S9 & S10 & S11 & S12

    Auth --> AuthSvc
    AgentAPI --> AgentSvc
    CostAPI --> CostSvc
    CropAPI --> CropSvc
    CycleAPI --> CycleSvc
    WeatherAPI --> WeatherSvc

    AgentSvc --> Advisor & ConvSvc
    Advisor --> FarmCtx & LLMMgr
    LLMMgr --> LLMProv & CB
    WeatherSvc --> QWeather & OpenMeteo

    S1 & S2 & S3 & S4 --> SkillCache
    S5 & S7 & S8 & S10 & S11 & S12 --> Pending
    AgentSvc --> Trace
    AgentAPI --> Limiter

    AuthSvc & CostSvc & CropSvc & CycleSvc --> MySQL
    ConvSvc & FarmCtx --> MySQL
```

---

## 2. 分层依赖图

```mermaid
flowchart TB
    subgraph "第 1 层: API 路由层"
        direction LR
        API["app/api/<br/>17 个路由文件<br/>+ deps.py DI"]
    end

    subgraph "第 2 层: Agent 系统层"
        direction LR
        Agent["app/agent/<br/>advisor · graph · tool_selector<br/>guardrails · prompt_registry"]
    end

    subgraph "第 3 层: Skill 系统层"
        direction LR
        Skills["app/agent/skills/<br/>12 个 Skill<br/>(skillify-sdk 加载)"]
    end

    subgraph "第 4 层: 服务层"
        direction LR
        Services["app/services/<br/>15 个 Service<br/>+ weather/ 子系统"]
    end

    subgraph "第 5 层: 数据模型层"
        direction LR
        Models["app/models/<br/>16 个 ORM Model"]
        Schemas["app/schemas/<br/>Pydantic Schema"]
    end

    subgraph "第 6 层: 基础设施层"
        direction LR
        Infra["app/infra/<br/>限流 · 熔断 · Trace<br/>写确认 · 缓存"]
    end

    subgraph "第 7 层: 核心层"
        direction LR
        Core["app/core/<br/>config · database · security<br/>logger · llm_client_manager"]
    end

    API --> Agent
    API --> Services
    API --> Infra
    API --> Core
    Agent --> Skills
    Agent --> Services
    Agent --> Core
    Skills --> Services
    Skills --> Infra
    Services --> Models
    Services --> Schemas
    Services --> Core
    Infra --> Core
    Infra --> Models
```

### 分层职责说明

| 层级 | 目录 | 职责 | 文件数 |
|------|------|------|--------|
| API 路由层 | `app/api/` | HTTP 入口，参数校验，调用 service 返回响应 | 17 + deps |
| Agent 系统层 | `app/agent/` | LangGraph 状态机编排，工具选择，Guardrails，Prompt 管理 | 8 |
| Skill 系统层 | `app/agent/skills/` | 12 个可执行 Skill，通过 skillify-sdk 加载为 LangChain Tool | 12 目录 |
| 服务层 | `app/services/` | 业务逻辑，事务编排，天气子系统 | 15 + weather/ |
| 数据模型层 | `app/models/` + `app/schemas/` | SQLAlchemy ORM 模型 + Pydantic 请求/响应 Schema | 16 + 11 |
| 基础设施层 | `app/infra/` | 限流、熔断、Trace 追踪、写操作确认、缓存 | 7 |
| 核心层 | `app/core/` | 配置、数据库连接、安全、日志、LLM 路由 | 7 |

---

## 3. 请求流转图

```mermaid
sequenceDiagram
    participant C as 客户端
    participant M as FastAPI (main.py)
    participant L as 限流器 (limiter)
    participant D as DI (deps.py)
    participant API as API 路由
    participant Svc as Service 层
    participant Adv as Advisor
    participant G as Guardrails
    participant TS as ToolSelector
    participant LLM as LLM Provider
    participant SK as Skill
    participant PA as PendingAction
    participant DB as MySQL

    C->>M: POST /agent/chat
    M->>L: 检查限流 (10/min)
    L-->>M: 通过
    M->>D: get_current_user() + get_current_farm()
    D->>DB: 验证 JWT → 查 User → 查 Farm
    D-->>M: User + Farm 注入
    M->>API: agent.chat()
    API->>Svc: agent_service.chat_with_agent()

    Svc->>Svc: 检查写操作待确认
    Svc->>Adv: invoke_advisor(query, farm_id)

    Adv->>G: 输入安全检查 (注入/敏感词)
    G-->>Adv: 通过

    Adv->>Adv: 加载对话历史
    Adv->>Adv: Composer 组合系统 Prompt（snippets + priority stack）

    loop LangGraph 循环 (max 15 步)
        Adv->>TS: 三层工具预过滤
        TS-->>Adv: 候选 Tool 列表
        Adv->>LLM: 绑定 Tools → LLM 调用
        LLM-->>Adv: AIMessage (含 tool_calls)

        alt 有 tool_calls
            Adv->>SK: 并行执行 Skills
            SK-->>Adv: SkillResult
            alt 写操作 Skill
                SK->>PA: 注册为待确认操作
                PA-->>SK: 返回确认消息
            end
        else 无 tool_calls
            Note over Adv: LLM 直接回复，退出循环
        end
    end

    Adv->>G: 输出 PII 过滤
    G-->>Adv: 安全响应

    Adv-->>Svc: AgentResponse
    Svc->>DB: 保存 AgentRecord + ConversationMessage
    Svc-->>API: ChatResponse
    API-->>M: JSON Response
    M-->>C: HTTP 200
```

---

## 4. Agent 内部架构图

```mermaid
flowchart TB
    subgraph "Agent 入口 (advisor.py)"
        Invoke["invoke_advisor()<br/>同步调用"]
        Stream["stream_advisor()<br/>SSE 流式"]
    end

    subgraph "安全层 (guardrails.py)"
        InputGuard["输入检查<br/>• SQL 注入检测<br/>• 敏感关键词过滤<br/>• 长度限制"]
        OutputGuard["输出过滤<br/>• 身份证号脱敏<br/>• 手机号脱敏<br/>• 邮箱脱敏<br/>• API Key 检测"]
    end

    subgraph "LangGraph 状态机 (graph.py)"
        LLMNode["_llm_node<br/>工具绑定 + Prompt 渲染<br/>+ LLM 调用"]
        ToolNode["_parallel_tool_node<br/>并发执行 Skills"]
        Cond{"有 tool_calls?"}
        EndNode["END"]
    end

    subgraph "工具选择器 (tool_selector.py)"
        Layer1["第 1 层: 正则匹配<br/>QUERY_PATTERNS"]
        Layer2["第 2 层: 关键词触发<br/>QUERY_TRIGGERS"]
        Layer3["第 3 层: LLM 意图分类<br/>fallback"]
        ChainMap["TOOL_CHAIN_MAP<br/>关联工具自动扩展"]
    end

    subgraph "Prompt 系统"
        Registry["PromptRegistry<br/>线程安全 · 版本管理<br/>热重载"]
        Renderer["PromptRenderer<br/>Jinja2 · 内置日期变量"]
        Composer["PromptComposer<br/>snippet 组合 · Priority Stack<br/>场景配置 · 去重"]
        Snippets["prompts/snippets/<br/>p1-language · p1-tool-guardrails<br/>p2-role · p2-capability<br/>p3-format · p3-style<br/>p4-context"]
        TaskTemplates["prompts/<br/>cost_parse · crop_template_parse<br/>cycle_parse · report<br/>config.yaml"]
        Composer --> Registry & Renderer & Snippets & TaskTemplates
    end

    subgraph "上下文工程"
        FarmCtx["farm_context_service.py<br/>• 活跃种植周期<br/>• 近期农事日志<br/>• 未结债务<br/>• 月度收支<br/>• 天气信息<br/>(5min TTL 缓存)"]
        ConvHist["conversation_service.py<br/>对话历史加载<br/>滑动窗口压缩"]
        DateCtx["date_context.py<br/>ContextVar 日期注入"]
    end

    Invoke & Stream --> InputGuard
    InputGuard --> ConvHist
    ConvHist --> FarmCtx
    FarmCtx --> LLMNode
    LLMNode --> Layer1
    Layer1 --> Layer2
    Layer2 --> Layer3
    Layer3 --> ChainMap
    ChainMap --> LLMNode
    LLMNode --> Renderer
    Renderer --> Registry
    Registry --> Templates

    LLMNode --> Cond
    Cond -->|是| ToolNode
    Cond -->|否| EndNode
    ToolNode --> LLMNode

    EndNode --> OutputGuard
```

### Agent 模块职责

| 文件 | 职责 |
|------|------|
| `advisor.py` | Agent 入口，提供同步和流式调用，处理 Guardrails 和对话历史 |
| `graph.py` | LangGraph StateGraph，`_llm_node` + `_parallel_tool_node`，最大 15 步递归 |
| `state.py` | `AgentState` TypedDict，`messages` 使用 `add_messages` reducer |
| `llm.py` | LLM 客户端工厂，优先 LLMClientManager，回退 config.yaml |
| `tool_selector.py` | 三层工具预过滤：正则 → 关键词 → LLM 意图，含 TOOL_CHAIN_MAP |
| `guardrails.py` | 输入安全（注入检测、敏感词）+ 输出 PII 过滤 |
| `prompt_registry.py` | 线程安全 Prompt 模板注册中心，支持版本管理和热重载 |
| `prompt_renderer.py` | Jinja2 渲染器，内置日期/时间变量 |
| `prompt_composer.py` | Prompt 组合器，按场景组合 snippet 片段渲染最终 prompt。Priority Stack 排序（P1-P4），snippet 去重，全局单例。设计参考 Anthropic Tool Design + PE Collective |
| `report.py` | 种植周期报告生成，通过 LLM + Tool 调用 |

### Prompt 加载流程

#### 三层架构总览

```mermaid
flowchart LR
    Composer["PromptComposer<br/>场景路由 · snippet 组合 · priority 排序"]
    Renderer["PromptRenderer<br/>Jinja2 渲染 · 变量注入"]
    Registry["PromptRegistry<br/>模板注册 · 热重载"]
    Composer --> Renderer --> Registry
```

#### 启动阶段（服务启动时执行一次）

```mermaid
flowchart LR
    A["get_registry()"] --> B["registry.reload(prompts_dir)"]
    B --> C["读取 config.yaml"]
    C --> D["加载 4 个 .j2 模板"]
    D --> E["get_composer()"]
    E --> F["扫描 snippets/ 目录"]
    E --> G["读取 compositions 段"]
    F --> H["Prompt 系统就绪"]
    G --> H

    style H fill:#22c55e,color:#fff
```

#### 运行时：两种组合模式

```mermaid
flowchart TB
    subgraph "模式 A：完整组合 system_base（graph.py）"
        direction LR
        A1["compose('system_base')"] --> A2["查 compositions 配置"]
        A2 --> A3["取 7 个 snippets"]
        A3 --> A4["去重 → 渲染 → 排序 P1→P4"]
        A4 --> A5["拼接 → 标题去重"]
        A5 --> A6["最终 system prompt"]
    end

    subgraph "模式 B：模板组合 cost_parse（cost.py）"
        direction LR
        B1["compose('cost_parse')"] --> B2["查 compositions 配置"]
        B2 --> B3["取 p1-language snippet"]
        B3 --> B4["渲染 snippet"]
        B4 --> B5["Registry 取任务模板"]
        B5 --> B6["渲染模板"]
        B6 --> B7["snippet + template 拼接"]
        B7 --> B8["标题去重"]
        B8 --> B9["最终 cost_parse prompt"]
    end

    style A6 fill:#22c55e,color:#fff
    style B9 fill:#22c55e,color:#fff
```

**5 个调用点：**

| 调用位置 | 场景 | Snippets | Task Template |
|----------|------|----------|---------------|
| `graph.py:227` | `system_base` | 7 个（完整组合） | — |
| `report.py:33` | `report` | p1-language | report.j2 |
| `cost.py:120` | `cost_parse` | p1-language | cost_parse.j2 |
| `crop.py:123` | `crop_template_parse` | p1-language | crop_template_parse.j2 |
| `cycle.py:152` | `cycle_parse` | p1-language | cycle_parse.j2 |

---

## 5. Skill 系统架构图

```mermaid
flowchart TB
    subgraph "Skill 加载器 (skillify-sdk)"
        SDK["SkillManager<br/>扫描 skills/ 目录<br/>加载为 LangChain StructuredTool"]
    end

    subgraph "只读 Skills (Read-Only, 可缓存)"
        direction TB
        R1["get_weather_forecast<br/>7天预报 + 灾害预警<br/>⏱ 30min TTL"]
        R2["get_farm_status<br/>农场综合状态<br/>⏱ 5min TTL"]
        R3["get_cost_summary<br/>收支余额汇总"]
        R4["get_cost_analytics<br/>费用趋势对比"]
        R5["get_crop_cycle_info<br/>周期阶段进度"]
        R6["get_recent_farm_logs<br/>近期农事日志"]
    end

    subgraph "写操作 Skills (Write, 需确认)"
        direction TB
        W1["create_cost_record<br/>记录收支"]
        W2["create_crop_cycle<br/>创建种植周期"]
        W3["create_crop_template<br/>创建作物模板"]
        W4["log_farm_activity<br/>记录农事活动"]
        W5["update_crop_stage<br/>更新生长阶段"]
        W6["settle_debt<br/>结算债务"]
    end

    subgraph "写操作确认机制 (pending_actions.py)"
        PAReg["注册待确认操作<br/>5min 超时"]
        PADetect["意图检测<br/>确认 / 取消 / 修改"]
        PAMsg["构建确认消息<br/>展示操作详情"]
    end

    subgraph "Skill 缓存 (skill_cache.py)"
        Cache["TTL Cache 装饰器<br/>只读 Skill 可选"]
    end

    subgraph "Skill 依赖的 Services"
        CostSvc["cost_service"]
        CropSvc["crop_service"]
        CycleSvc["cycle_service"]
        LogSvc["log_service"]
        DebtSvc["debt_service"]
        FarmCtx["farm_context_service"]
        WeatherSvc["weather_service"]
    end

    SDK --> R1 & R2 & R3 & R4 & R5 & R6
    SDK --> W1 & W2 & W3 & W4 & W5 & W6

    R1 --> Cache --> WeatherSvc
    R2 --> Cache --> FarmCtx
    R3 --> CostSvc
    R4 --> CostSvc
    R5 --> CycleSvc
    R6 --> LogSvc

    W1 --> PAReg
    W2 --> PAReg
    W3 --> PAReg
    W4 --> PAReg
    W5 --> PAReg
    W6 --> PAReg
    PAReg --> PADetect --> PAMsg

    W1 --> CostSvc
    W2 --> CycleSvc
    W3 --> CropSvc
    W4 --> LogSvc
    W5 --> CycleSvc
    W6 --> DebtSvc
```

### 12 个 Skill 清单

| Skill | 类型 | 功能 | 缓存 | 触发词 |
|-------|------|------|------|--------|
| `get_weather_forecast` | 只读 | 7天天气预报 + 灾害预警 | 30min | 天气、预报、下雨 |
| `get_farm_status` | 只读 | 农场综合状态（周期/日志/债务/收支/天气） | 5min | 农场状态、概况、总览 |
| `get_cost_summary` | 只读 | 收支余额汇总 | - | 账户余额、收支、总共 |
| `get_cost_analytics` | 只读 | 费用趋势分析 | - | 费用趋势、分析、对比 |
| `get_crop_cycle_info` | 只读 | 种植周期阶段进度 | - | 种植、周期、阶段 |
| `get_recent_farm_logs` | 只读 | 近期农事活动日志 | - | 日志、记录、最近操作 |
| `create_cost_record` | **写** | 记录收/支条目 | 禁止 | 记账、花费、买了 |
| `create_crop_cycle` | **写** | 创建新种植周期 | 禁止 | 开始种植、新周期 |
| `create_crop_template` | **写** | 创建作物模板 | 禁止 | 新作物、添加模板 |
| `log_farm_activity` | **写** | 记录农事操作 | 禁止 | 记录、操作、施肥/打药 |
| `update_crop_stage` | **写** | 更新作物生长阶段 | 禁止 | 更新阶段、进入下一阶段 |
| `settle_debt` | **写** | 结算债务记录 | 禁止 | 还钱、结算、清账 |

---

## 6. LLM 多 Provider 路由图

```mermaid
flowchart TB
    subgraph "LLM 客户端管理器 (llm_client_manager.py)"
        Mgr["LLMClientManager<br/>加权随机选择 + 熔断"]
        Watcher["FileWatcher<br/>watchfiles 监听<br/>providers.json 热重载"]
        Fallback["Fallback<br/>providers.json 加载失败时<br/>回退到 config.yaml"]
    end

    subgraph "Provider 配置 (providers.json)"
        P1["Provider: ollama<br/>weight: 8<br/>models: 4"]
        P2["Provider: nvidia<br/>weight: 2<br/>models: 3"]
        P3["Provider: dashscope<br/>weight: 1<br/>models: 2"]
    end

    subgraph "熔断器 (circuit_breaker.py)"
        Cool["COOLING<br/>正常可用"]
        Warm["WARMING<br/>错误计数中"]
        Dead["DEAD<br/>指数退避冷却"]
        Cool -->|连续失败| Warm
        Warm -->|达到阈值| Dead
        Dead -->|冷却时间到| Cool
        Warm -->|调用成功| Cool
    end

    subgraph "外部 LLM 服务"
        Ollama["Ollama<br/>本地模型<br/>qwen3:8b 等"]
        NVIDIA["NVIDIA NIM<br/>云端 GPU<br/>qwen3-30b 等"]
        DashScope["阿里 DashScope<br/>qwen-max 等"]
    end

    Mgr --> Watcher
    Mgr --> Fallback
    Watcher --> P1 & P2 & P3

    Mgr -->|"weight=8 优先"| Ollama
    Mgr -->|"weight=2"| NVIDIA
    Mgr -->|"weight=1"| DashScope

    Ollama & NVIDIA & DashScope --> Cool

    Mgr -->|"选择 Provider"| Cool
    Cool -->|"可用"| Mgr
    Dead -->|"熔断，跳过"| Mgr
```

### 路由策略说明

| 机制 | 说明 |
|------|------|
| **加权随机** | 按 weight 比例分配请求，ollama(8) : nvidia(2) : dashscope(1) |
| **模型级熔断** | 每个 model 独立维护 COOLING/WARMING/DEAD 三态 |
| **指数退避** | DEAD 状态后冷却时间指数增长 |
| **热重载** | watchfiles 监听 providers.json 变更，无需重启 |
| **Fallback** | providers.json 加载失败自动回退 config.yaml |

---

## 7. 天气双 Provider 架构图

```mermaid
flowchart TB
    subgraph "天气服务门面 (weather_service.py)"
        Facade["WeatherService<br/>统一对外接口<br/>兼容旧格式"]
    end

    subgraph "策略层 (weather/strategy.py)"
        Strategy["WeatherStrategy<br/>• Provider 路由<br/>• 故障自动切换<br/>• 预警注入<br/>• 10min TTL 缓存"]
    end

    subgraph "Provider 层"
        direction LR
        QW["QWeatherProvider<br/>(weather/qweather.py)<br/>• API Key 认证<br/>• HMAC 签名认证<br/>• 7天预报 + 实时<br/>• 中国城市优化"]
        OM["OpenMeteoProvider<br/>(weather/open_meteo.py)<br/>• 免费无 Key<br/>• 全球覆盖<br/>• 16天预报"]
    end

    subgraph "预警系统"
        AlertScraper["alert_scraper.py<br/>中国气象局预警爬取"]
        AlertData["WeatherAlert<br/>• 预警级别<br/>• 预警类型<br/>• 有效时间"]
    end

    subgraph "缓存层 (weather/cache.py)"
        WCache["TTL Cache<br/>10 分钟过期<br/>按城市缓存"]
    end

    subgraph "数据类型 (weather/base.py)"
        Types["WeatherData<br/>DailyForecast<br/>AirQuality<br/>WeatherAlert<br/>ProviderError"]
    end

    Facade --> Strategy
    Strategy --> QW
    Strategy --> OM
    QW -->|"主 Provider"| WCache
    OM -->|"备用 Provider"| WCache

    Strategy --> AlertScraper
    AlertScraper --> AlertData
    Strategy --> AlertData

    QW --> Types
    OM --> Types
    AlertData --> Types
```

### 天气策略说明

| 场景 | 行为 |
|------|------|
| **正常请求** | 优先 QWeather → 缓存命中直接返回 |
| **QWeather 失败** | 自动切换 Open-Meteo |
| **预警注入** | 爬取结果自动合并到预报响应中 |
| **缓存** | 10min TTL，按城市独立缓存 |

### 天气子系统文件

| 文件 | 职责 |
|------|------|
| `weather_service.py` | 门面类，对外统一接口，兼容旧数据格式 |
| `weather/base.py` | 数据类型定义：WeatherData, DailyForecast, AirQuality, WeatherAlert, ProviderError |
| `weather/qweather.py` | 和风天气 Provider，支持 API Key 和 HMAC 签名两种认证 |
| `weather/open_meteo.py` | Open-Meteo 免费 Provider，全球覆盖 |
| `weather/strategy.py` | 路由策略：Provider 选择、故障切换、预警注入、缓存 |
| `weather/cache.py` | TTL 缓存实现 |
| `weather/alert_scraper.py` | 中国气象局天气预警爬取 |

---

## 8. 数据模型 ER 图

```mermaid
erDiagram
    User ||--o{ Farm : owns
    User ||--o{ Conversation : has
    User ||--o{ UserSetting : has
    User ||--o{ FeedbackRecord : writes
    User {
        int id PK
        string phone UK
        string password_hash
        string role "user/admin"
        string status "active/disabled"
        datetime created_at
    }

    Farm ||--o{ CropTemplate : defines
    Farm ||--o{ CropCycle : runs
    Farm ||--o{ FarmLog : records
    Farm ||--o{ CostRecord : tracks
    Farm ||--o{ CostCategory : groups
    Farm ||--o{ Conversation : "hosts"
    Farm ||--o{ AgentRecord : "produces"
    Farm ||--o{ TokenDailyStats : "consumes"
    Farm {
        int id PK
        string name
        string location
        int user_id FK
        datetime created_at
    }

    CropTemplate ||--o{ GrowthStage : has
    CropTemplate ||--o{ CropCycle : "instantiates"
    CropTemplate {
        int id PK
        string name
        string crop_type
        int farm_id FK
        json growth_config
        datetime created_at
    }

    GrowthStage {
        int id PK
        int template_id FK
        string name
        int order_index
        int duration_days
    }

    CropCycle ||--o{ CycleStage : goes_through
    CropCycle {
        int id PK
        int template_id FK
        int farm_id FK
        string season_name
        date start_date
        date end_date
        string status "active/completed/archived"
    }

    CycleStage {
        int id PK
        int cycle_id FK
        string stage_name
        int order_index
        date actual_start
        date actual_end
        string status
    }

    CostCategory ||--o{ CostRecord : categorizes
    CostCategory {
        int id PK
        int farm_id FK
        string name
        string type "income/expense"
        string icon
    }

    CostRecord {
        int id PK
        int farm_id FK
        int category_id FK
        float amount
        string type "income/expense"
        string counterparty "债务对方"
        date due_date "还款日期"
        date settled_at "结算日期"
        date record_date
        string note
    }

    Conversation ||--o{ ConversationMessage : contains
    Conversation {
        int id PK
        int user_id FK
        int farm_id FK
        string status "active/closed"
        datetime expires_at "24h 过期"
    }

    ConversationMessage {
        int id PK
        int conversation_id FK
        string role "user/assistant/system"
        text content
        json tool_calls
        datetime created_at
    }

    AgentRecord {
        int id PK
        int farm_id FK
        int conversation_id FK
        string type "chat/daily_advice/report"
        text content
        json metadata
        datetime created_at
    }

    FeedbackRecord {
        int id PK
        int user_id FK
        int agent_record_id FK
        string rating "good/bad"
        text correction
        datetime created_at
    }

    TraceRecord {
        int id PK
        string request_id
        int farm_id
        string call_type "llm/skill"
        string model_name
        text input_data
        text output_data
        int input_tokens
        int output_tokens
        int duration_ms
        datetime created_at
    }

    TokenDailyStats {
        int id PK
        int farm_id FK
        string model_name
        string call_type
        date stat_date
        int total_input_tokens
        int total_output_tokens
        int total_calls
    }

    GuardrailsLog {
        int id PK
        string direction "input/output"
        string rule_name
        text original_content
        text filtered_content
        datetime created_at
    }

    IdempotencyKey {
        int id PK
        string key UK
        string status
        datetime expires_at
    }

    UserSetting {
        int id PK
        int user_id FK
        string default_city
        float latitude
        float longitude
        json preferences
    }
```

---

## 9. 模块职责清单

### app/core/ — 核心层

| 文件 | 职责 |
|------|------|
| `settings/` | pydantic-settings 配置中心，加载优先级：init_settings > env_vars > config.yaml |
| `database.py` | SQLAlchemy MySQL 引擎 + Session 工厂，连接池启用 pre_ping/recycle |
| `security.py` | JWT 创建/验证 (PyJWT) + bcrypt 密码哈希 |
| `logger.py` | 结构化日志：stdout 彩色 + rotating files，request_id 上下文变量 |
| `seed.py` | 数据库初始化：默认农场、管理员用户、字段迁移 |
| `date_context.py` | ContextVar 日期注入，从 X-Current-Date Header 读取 |
| `json_repair.py` | JSON 解析工具：从 Markdown 代码块提取、自动修复 LLM 输出错误 |
| `llm_client_manager.py` | 多 Provider LLM 路由，加权随机选择，模型级熔断，文件热重载 |

### app/models/ — 数据模型层 (16 个模型)

| 模型 | 表名 | 职责 |
|------|------|------|
| `User` | users | 用户认证（手机号+密码），角色(user/admin)，状态(active/disabled) |
| `Farm` | farms | 多租户农场实体，关联 user_id |
| `CropTemplate` | crop_templates | 作物定义模板，含可配置生长阶段 |
| `GrowthStage` | growth_stages | 生长阶段定义（名称、顺序、天数） |
| `CropCycle` | crop_cycles | 种植周期（季），关联模板和农场 |
| `CycleStage` | cycle_stages | 周期中的实际阶段记录 |
| `FarmLog` | farm_logs | 农事活动日志 |
| `CostRecord` | cost_records | 收支记录，支持债务（对方、到期日、结算日） |
| `CostCategory` | cost_categories | 每农场收支分类，含图标 |
| `Conversation` | conversations | 对话会话（active/closed，24h 过期） |
| `ConversationMessage` | conversation_messages | 对话消息（含 tool_calls JSON） |
| `AgentRecord` | agent_records | Agent 输出记录（chat/daily_advice/report） |
| `FeedbackRecord` | feedback_records | 用户对 AI 回复的评价（good/bad + 纠正建议） |
| `TraceRecord` | trace_records | LLM/Skill 调用追踪（输入/输出/耗时/Token） |
| `TokenDailyStats` | token_daily_stats | 每日 Token 使用统计（按农场/模型/类型） |
| `GuardrailsLog` | guardrails_logs | 输入/输出安全拦截日志 |
| `IdempotencyKey` | idempotency_keys | 幂等性缓存，自动清理 |
| `UserSetting` | user_settings | 用户偏好（默认城市、经纬度） |

### app/schemas/ — Pydantic Schema 层

| 文件 | 包含 Schema | 职责 |
|------|------------|------|
| `agent.py` | ChatRequest, ChatResponse, PendingActionResponse, AdviceItem, DailyAdviceResponse, ReportRequest, ReportResponse 等 | Agent 对话/建议/报告的请求响应 |
| `auth.py` | LoginRequest, RegisterRequest, TokenResponse, UpdateProfileRequest, UserResponse | 认证相关 |
| `cost.py` | CostRecordCreate, CostRecordResponse, CycleProfit, YearlySummary | 记账 CRUD + 分析 |
| `cost_category.py` | CostCategory 相关 Schema | 分类管理 |
| `crop.py` | CropTemplateBase/Create/Response, GrowthStageBase/Create/Response | 作物模板 |
| `cycle.py` | CropCycleCreate/Response/ListResponse, CycleStageResponse | 种植周期 |
| `log.py` | FarmLogCreate, FarmLogResponse | 农事日志 |
| `feedback.py` | Feedback 相关 Schema | AI 反馈 |
| `settings.py` | UserSettings Schema | 用户设置 |
| `common.py` | PaginatedResponse | 通用分页响应 |
| `admin_user.py` | AdminUser Schema | 管理员用户管理 |

### app/api/ — 路由层

| 文件 | 路径前缀 | 关键端点 |
|------|---------|---------|
| `auth.py` | `/auth` | POST /register, /login, GET /me, PUT /me |
| `agent.py` | `/agent` | POST /chat, /chat/stream (SSE), GET /daily, POST /daily/refresh, POST /report, GET /conversations, /advice-history, /report-history |
| `crop.py` | `/crops` | 作物模板 CRUD |
| `cycle.py` | `/cycles` | 种植周期 CRUD |
| `cost.py` | `/costs` | 收支 CRUD + 分析 |
| `cost_categories.py` | `/cost-categories` | 分类 CRUD |
| `log.py` | `/logs` | 农事日志 CRUD |
| `debt.py` | `/debts` | 债务管理 |
| `weather.py` | `/weather` | 天气预报 |
| `feedback.py` | `/feedback` | AI 反馈提交 |
| `user_settings.py` | `/user-settings` | 用户偏好 |
| `admin.py` | `/admin` | 管理面板 |
| `admin_config.py` | `/admin/config` | LLM 配置管理 + 热重载 |
| `admin_stats.py` | `/admin/stats` | 统计数据 |
| `admin_trace.py` | `/admin/trace` | Trace 数据查看 |
| `admin_users.py` | `/admin/users` | 用户管理 |
| `deps.py` | (共享) | DI: get_db, get_current_user, get_current_farm, verify_resource_owner, require_admin |

### app/services/ — 服务层

| 文件 | 职责 |
|------|------|
| `agent_service.py` | Agent 编排：chat, stream_chat, get_daily_advice, refresh_daily_advice, generate_report, 历史查询 |
| `auth_service.py` | 用户注册（自动创建 Farm）、登录、用户查询 |
| `conversation_service.py` | 对话生命周期：创建/关闭会话、保存消息、加载历史 |
| `cost_service.py` | 收支 CRUD + 分析 |
| `cost_category_service.py` | 分类管理 |
| `crop_service.py` | 作物模板管理 |
| `cycle_service.py` | 种植周期管理 |
| `debt_service.py` | 债务结算 |
| `farm_context_service.py` | 构建农场状态摘要（活跃周期/日志/债务/月度收支/天气），5min TTL 缓存 |
| `feedback_service.py` | 反馈记录 |
| `log_service.py` | 农事日志管理 |
| `quota_service.py` | Token 每日配额检查 |
| `weather_service.py` | 天气门面：双 Provider 策略，旧格式兼容 |
| `weather/base.py` | 天气数据类型定义 |
| `weather/qweather.py` | 和风天气 Provider |
| `weather/open_meteo.py` | Open-Meteo Provider |
| `weather/strategy.py` | Provider 路由、故障切换、预警注入、缓存 |
| `weather/cache.py` | 天气数据 TTL 缓存 |
| `weather/alert_scraper.py` | 天气预警爬取 |

### app/infra/ — 基础设施层

| 文件 | 职责 |
|------|------|
| `limiter.py` | 全局 SlowAPI 限流器（IP 级） |
| `circuit_breaker.py` | 三态熔断器（CLOSED/OPEN/HALF_OPEN），指数退避重试 |
| `pending_actions.py` | 写操作确认系统：内存存储（5min 超时），意图检测（确认/取消/修改） |
| `trace_collector.py` | 异步 Trace 收集：后台 flush 批量写入 MySQL |
| `trace_context.py` | ContextVar 追踪上下文：request_id, session_id, farm_id, round |
| `trace_dao.py` | 批量 INSERT + Token 统计 UPSERT |
| `trace_cleaner.py` | TTL 清理：Trace 7天，Token 统计 90天，每日执行 |
| `skill_cache.py` | Skill 结果 TTL 缓存装饰器 |

### prompts/ — Prompt 模板（Composer + Snippet 架构）

**设计理念：** 基于 Anthropic Tool Design、LangChain Context Engineering、PE Collective Priority Stack 等成熟实践。

核心原则：
- **工具路由不在 prompt 中** — tool_selector.py 三层过滤 + Tool.description 自动注入已覆盖，prompt 只保留行为约束（"禁止编造数据"）
- **可组合 Snippet** — 按关注点拆分为 p1-p4 优先级片段，PromptComposer 按场景组合
- **Priority Stack** — P1 Safety > P2 Accuracy > P3 Format > P4 Context，消除多个"最高优先级"矛盾

| 文件 | 职责 |
|------|------|
| `config.yaml` | Prompt 配置：templates（任务模板）+ compositions（场景组合） |
| `cost_parse.j2` | 记账解析任务模板 |
| `crop_template_parse.j2` | 作物模板解析任务模板 |
| `cycle_parse.j2` | 种植周期解析任务模板 |
| `report.j2` | 报告生成任务模板 |
| `snippets/p1-language.j2` | P1 Safety：语言规则（全程中文） |
| `snippets/p1-tool-guardrails.j2` | P1 Safety：工具调用安全护栏（禁止编造数据） |
| `snippets/p2-role.j2` | P2 Accuracy：角色定义（农业技术顾问） |
| `snippets/p2-capability.j2` | P2 Accuracy：能力范围 |
| `snippets/p3-format.j2` | P3 Format：回复格式约束 |
| `snippets/p3-style.j2` | P3 Format：回复风格 |
| `snippets/p4-context.j2` | P4 Context：动态上下文（时间/用户信息，Jinja2 变量注入） |

**场景组合示例：**

| 场景 | Snippets | Task Template |
|------|----------|---------------|
| `system_base` | p1-language + p1-tool-guardrails + p2-role + p2-capability + p3-format + p3-style + p4-context | — |
| `cost_parse` | p1-language | cost_parse.j2 |
| `crop_template_parse` | p1-language | crop_template_parse.j2 |
| `cycle_parse` | p1-language | cycle_parse.j2 |
| `report` | p1-language | report.j2 |

### 其他

| 目录/文件 | 职责 |
|-----------|------|
| `skillify-sdk/` | 本地 SDK 包，Skill 加载框架，扫描目录并注册为 LangChain Tool |
| `data/` | 静态数据（天气城市代码映射） |
| `scripts/` | 运维脚本（数据库备份、迁移） |
| `config.yaml` | 运行时配置（YAML，gitignored） |
| `providers.json` | 多 Provider LLM 路由配置（3 Provider, 9 Model） |
| `model_list.json` | 可用 LLM 模型目录 |
| `requirements.txt` | Python 依赖（20 个包） |
| `Dockerfile` | 生产容器（Python 3.11, uvicorn） |
