---
last_updated: 2026-05-27
status: active
---

# Farm-Manager 系统演进路线图

> 全局视角：从当前状态到目标架构的分阶段演进计划。

---

## 一、当前架构全貌（2026-05）

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户端 (规划中)                           │
│              React Native App / 微信小程序                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP
┌────────────────────────────▼────────────────────────────────────┐
│                     Admin Web (React+TS+Vite)                    │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │Dashboard │ │ 链路追踪   │ │ 接口调试  │ │ Skill/Prompt管理 │  │
│  └──────────┘ └───────────┘ └──────────┘ └──────────────────┘  │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐                       │
│  │ Gantt    │ │ 种植周期   │ │ Token统计│                       │
│  │ Timeline │ │ 管理      │ │ 监控     │                       │
│  └──────────┘ └───────────┘ └──────────┘                       │
└────────────────────────────┬────────────────────────────────────┘
                             │ REST API
┌────────────────────────────▼────────────────────────────────────┐
│                   FastAPI 后端 (v1, ~8,500 行)                   │
│                                                                  │
│  api/                          services/                         │
│  ├── agent.py (对话入口)        ├── agent_service.py              │
│  ├── admin_trace.py            ├── conversation_service.py       │
│  ├── cost/crop/cycle/log       ├── cost/crop/cycle_service.py    │
│  ├── weather.py                ├── weather_service.py            │
│  └── user_settings.py          └── quota_service.py              │
│                                                                  │
│  agents/ (LangGraph Agent)     core/ (19个模块，待拆分)           │
│  ├── graph.py (主图)            ├── config/database/logger       │
│  ├── advisor.py                ├── llm/guardrails/prompt_*       │
│  ├── report.py                 ├── trace_*/circuit_breaker       │
│  └── state.py                  ├── limiter/skill_cache           │
│                                 └── term_whitelist (死代码)       │
│                                                                  │
│  skills/ (10个Skill)           models/  schemas/                 │
│  ├── cost-summary              6张核心表  Pydantic模型            │
│  ├── create-cost-record                                            │
│  ├── crop-cycle / update-crop-stage                                │
│  ├── weather / farm-logs / log-farm-activity                       │
│  ├── cost-analytics / settle-debt                                  │
│  └── create-crop-cycle                                             │
│                                                                  │
│  prompts/                      skillify-sdk (Skill引擎)          │
│  ├── base.j2 + config.yaml     ├── Skill注册/匹配/执行            │
│  ├── cost_parse.j2             ├── 缓存 + 熔断                   │
│  └── report.j2                                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      SQLite (单文件, ~6张表)                      │
│  farms | crops | cycles | costs | cost_categories | logs         │
│  conversations | conversation_messages | trace_records           │
│  token_stats | guardrails_logs | idempotency_keys | agents       │
└─────────────────────────────────────────────────────────────────┘

外部依赖: DashScope(Qwen) | LangSmith(观测) | Open-Meteo(天气)
```

---

## 二、已规划变更（OpenSpec 提案，待实施）

```
                    ┌──────────────────────┐
                    │  ① Architecture      │
                    │  Cleanup             │
                    │  死代码删除           │
                    │  core/ → 三包拆分     │
                    │  prompt 单一数据源    │
                    └──────────┬───────────┘
                               │ 必须先完成
                    ┌──────────▼───────────┐
                    │  ② Storage Redesign  │
                    │  多用户支持           │
                    │  用户认证(JWT)        │
                    │  反馈收集             │
                    │  SQLite WAL + 备份    │
                    └──────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
   ┌──────────▼──────┐ ┌──────▼──────────┐ ┌──▼──────────────┐
   │  ③ Dual Weather │ │  ④ Session &    │ │  ⑤ Context      │
   │  Provider       │ │  Context        │ │  Engineering     │
   │  和风天气+OpenMeteo│ │  对话管理       │ │  (后续规划)      │
   │  预警爬虫        │ │  多轮上下文注入  │ │  上下文压缩      │
   │  API Key 统一管理│ │  用户信息注入    │ │  渐进式加载      │
   └─────────────────┘ └─────────────────┘ └──────────────────┘
```

### 执行顺序

| 优先级 | Change | 核心价值 | 风险 | 工作量 |
|-------|--------|---------|------|-------|
| P0 | ① Architecture Cleanup | 架构清晰，为后续所有变更铺路 | import路径变更(30+处) | 25 tasks |
| P0 | ② Storage Redesign | 多用户基础，数据安全 | 数据库迁移，API认证层 | 40 tasks |
| P1 | ③ Dual Weather | 农业核心功能(预警) | Provider路由复杂度 | 52 tasks |
| P1 | ④ Session & Context | 多轮对话，用户体验 | 对话持久化 | 30 tasks |
| P2 | ⑤ Context Engineering | 长会话性能，成本控制 | 研究型，方案待定 | TBD |

---

## 三、目标架构（Phase 3 完成后）

```
┌──────────────────────────────────────────────────────────────────┐
│                        客户端层                                   │
│                                                                  │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐    │
│   │ React Native │   │  微信小程序   │   │  Admin Web       │    │
│   │ App (农户端)  │   │  (轻量入口)   │   │  (管理/调试)     │    │
│   └──────┬───────┘   └──────┬───────┘   └────────┬─────────┘    │
│          │                  │                     │              │
└──────────┼──────────────────┼─────────────────────┼──────────────┘
           │                  │                     │
           ▼                  ▼                     ▼
┌──────────────────────────────────────────────────────────────────┐
│                       API Gateway (FastAPI)                       │
│                                                                  │
│   ┌──────────────────────────────────────────────────────────┐   │
│   │                    Auth Middleware                        │   │
│   │    JWT校验 → 用户识别 → 农场隔离 → 权限检查               │   │
│   └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│   api/                                                          │
│   ├── auth/          注册·登录·Token刷新                         │
│   ├── agent/         对话·流式·会话管理                          │
│   ├── farm/          农场信息·设置                                │
│   ├── crop/          作物·种植周期                                │
│   ├── cost/          成本·记账·债务                              │
│   ├── weather/       天气预报·预警·空气质量                      │
│   ├── feedback/      AI回复评价                                  │
│   └── admin/         链路追踪·Skill管理·系统配置                  │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                      Service 层                                   │
│                                                                  │
│   services/                                                     │
│   ├── agent_service.py        ─── LangGraph 编排                  │
│   ├── conversation_service.py ─── 会话管理·历史加载               │
│   ├── weather_service.py      ─── 多 Provider 路由                │
│   ├── feedback_service.py     ─── 评价收集                        │
│   ├── cost/crop/cycle/log     ─── 业务 CRUD                      │
│   └── quota_service.py        ─── 用量控制                        │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                    Agent 层 (app/agent/)                          │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │              LangGraph Agent (graph.py)                 │    │
│   │                                                         │    │
│   │  ┌─────┐    ┌──────────┐    ┌───────┐    ┌──────────┐  │    │
│   │  │ LLM │───▶│ Guardrails│───▶│ Tools │───▶│ Reporter │  │    │
│   │  │Node │    │ (输入输出) │    │ (Skills)│   │ (报告生成)│  │    │
│   │  └─────┘    └──────────┘    └───────┘    └──────────┘  │    │
│   │       │                                      │          │    │
│   │       ▼                                      ▼          │    │
│   │  ┌──────────┐                         ┌──────────┐     │    │
│   │  │ Prompt   │                         │ Advisor  │     │    │
│   │  │ Renderer │                         │ (意图分析)│     │    │
│   │  └──────────┘                         └──────────┘     │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│   skills/ (10+ Skill)                                           │
│   ├── 只读: cost-summary, cost-analytics, crop-cycle,            │
│   │         farm-logs, weather                                   │
│   └── 写操作: create-cost-record, create-crop-cycle,             │
│              update-crop-stage, log-farm-activity, settle-debt    │
│                                                                  │
│   prompt_registry.py + prompt_renderer.py (单一数据源: .j2文件)   │
│   llm.py + guardrails.py (LLM调用 + 安全护栏)                    │
│   state.py (Agent 状态定义)                                      │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                  基础设施层                                        │
│                                                                  │
│   core/ (全局基础)              infra/ (可观测性+运维)             │
│   ├── config.py                ├── trace_collector.py             │
│   ├── database.py (WAL)        ├── trace_dao.py                  │
│   ├── security.py (JWT)        ├── trace_context.py              │
│   ├── logger.py                ├── trace_cleaner.py              │
│   ├── date_context.py          ├── circuit_breaker.py            │
│   ├── json_repair.py           ├── limiter.py                    │
│   └── seed.py                  ├── pending_actions.py            │
│                                 └── skill_cache.py               │
│                                                                  │
│   skillify-sdk/ (独立包)                                         │
│   └── Skill 注册·匹配·执行·缓存·熔断                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                     数据层 (SQLite WAL)                           │
│                                                                  │
│   用户域              农业业务域           Agent域                │
│   ┌────────────┐    ┌─────────────┐    ┌───────────────┐        │
│   │ users      │    │ farms       │    │ conversations │        │
│   │ user_oauth │    │ crops       │    │ conv_messages │        │
│   │            │    │ cycles      │    │ agent_records │        │
│   │            │    │ costs       │    │ feedback      │        │
│   │            │    │ cost_cat    │    │ guardrails_log│        │
│   │            │    │ logs        │    │ token_stats   │        │
│   └────────────┘    └─────────────┘    └───────────────┘        │
│                                                                  │
│   定时备份: 在线热备 + 7天滚动保留                                 │
└──────────────────────────────────────────────────────────────────┘

外部服务:
┌─────────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐
│ DashScope   │  │ 和风天气      │  │ Open-Meteo│  │ LangSmith │
│ (Qwen LLM)  │  │ (中国气象数据) │  │ (全球天气) │  │ (链路观测) │
└─────────────┘  └──────────────┘  └───────────┘  └───────────┘
```

---

## 四、分阶段演进计划

### Phase 1: 架构清理 (当前 → 1周)

> 目标：消除技术债，为所有后续工作铺路

```
当前状态                              Phase 1 完成后
─────────                             ──────────────
core/ (19个模块混在一起)               core/ (7个基础模块)
                                      agent/ (Agent领域)
                                      infra/ (可观测性)

app/agents/ (旧名)                    app/agent/ (重命名)
_DEFAULT_PROMPTS (双数据源)           prompts/*.j2 (单一数据源)
term_whitelist.py (死代码)            已删除
farm_id=1 硬编码                      仍为 1 (Phase 2 处理)
```

**关键交付物:**
- [x] OpenSpec 提案: `backend-architecture-cleanup`
- [ ] 执行 `/opsx:apply backend-architecture-cleanup`
- [ ] 全量测试通过 + import路径零残留

---

### Phase 2: 多用户 + 数据安全 (1-2周)

> 目标：支持多用户登录，数据隔离，生产级数据库配置

```
Phase 1 完成后                        Phase 2 完成后
─────────                             ──────────────
无认证                                JWT 认证
farm_id=1 硬编码                       user_id → farm_id 动态
SQLite 默认模式                        SQLite WAL + 定时备份
单用户                                多用户隔离
无反馈收集                             feedback_records 表
advice + report 分开                   合并为 agent_records
```

**关键交付物:**
- [x] OpenSpec 提案: `storage-redesign-multi-user`
- [ ] 执行 `/opsx:apply storage-redesign-multi-user`
- [ ] 用户注册/登录接口 + JWT 中间件
- [ ] 数据迁移脚本
- [ ] WAL 配置 + 备份脚本

---

### Phase 3: 功能增强 (2-4周)

> 目标：完善核心农业功能，提升对话质量

```
包含:
├── ③ Dual Weather Provider
│   ├── 和风天气接入
│   ├── 中国天气网预警爬虫
│   ├── API Key 统一管理 (SecretsConfig)
│   └── 空气质量查询
│
├── ④ Session & Context
│   ├── 多轮对话历史注入
│   ├── 用户上下文 (位置/季节/称呼) 注入
│   └── 会话生命周期管理
│
├── Function Calling 迁移 ✅
│   ├── Skill 从文本匹配 → Tool Calling
│   ├── 并行 Tool 调用
│   └── Tool Selection 优化 (description + prompt 映射表)
│
└── Tool RAG 预筛选 (Step 1a)
    ├── Keyword Pre-filter 模块
    ├── 候选 Tool 2-3 个精准注入
    └── 弱模型 tool selection 准确率 ↑↑
```

**关键交付物:**
- [x] OpenSpec 提案: `dual-weather-provider`
- [x] OpenSpec 提案: `session-management-and-context-injection`
- [x] Function Calling 迁移 (`function-calling-migration`)
- [x] Tool Selection Fix (`fc-tool-selection-fix`)
- [ ] 执行 dual-weather + session-context apply
- [ ] Tool RAG 预筛选模块

---

### Phase 4: 智能化 (1-2月)

> 目标：基于反馈数据持续优化 Agent 表现

```
Phase 3 完成后                        Phase 4 目标
─────────                             ──────────────
Skill 文本匹配/Function Calling       Skill 精准路由
固定 Prompt                           动态 Prompt (基于用户画像)
无学习                                基于反馈的 Prompt 优化
单 Agent                              多 Agent 协作 (可选)
```

**规划方向:**

| 方向 | 描述 | 依赖 |
|------|------|------|
| RLHF 循环 | 利用 feedback_records 评估 Prompt 质量，人工标注 + 自动评分 | Phase 2 feedback 表 |
| Prompt A/B 测试 | 同一意图多版本 Prompt，按效果自动切换 | RLHF 数据 |
| 个性化记忆 | 用户偏好、历史操作模式 → 注入 prompt | Phase 2 多用户 |
| 多 Agent 协作 | 种植顾问 + 气象分析师 + 财务顾问 分工 | Function Calling 稳定 |
| 知识库 (RAG) | 作物种植指南、病虫害图谱 → 检索增强 | 知识库数据源 |

---

### Phase 5: 规模化 (2-3月)

> 目标：移动端上线，用户增长，系统稳定运行

```
Phase 4 完成后                        Phase 5 目标
─────────                             ──────────────
Admin Web 仅                          + React Native App
SQLite 单文件                         考虑 PostgreSQL (用户增长后)
单机部署                              容器化 + CI/CD
中文仅                                多语言 (可选)
```

**规划方向:**

| 方向 | 描述 | 触发条件 |
|------|------|---------|
| 移动端 App | React Native 农户端 | Phase 3 完成 |
| 微信小程序 | 轻量入口，分享传播 | App 稳定后 |
| 数据库迁移 | SQLite → PostgreSQL | 并发 > 50 或数据 > 1GB |
| 容器化 | Docker + docker-compose | 部署需求 |
| CI/CD | GitHub Actions 测试+部署 | 团队协作需求 |

---

## 五、上下文工程演进路径

> 基于 Lance Martin (LangChain) 上下文工程四维框架：**Write / Select / Compress / Isolate**
> 参考: [Context Engineering for Agents](https://rlancemartin.github.io/2025/06/23/context_engineering/) | [ToolRAG 论文](https://arxiv.org/abs/2410.14594) | [12-Factor Agents](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md)

### 框架全景

```
                    上下文工程四维策略
                    ────────────────
    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  Write   │  │  Select  │  │ Compress │  │ Isolate  │
    │ 写出上下文│  │ 选入上下文│  │ 压缩上下文│  │ 隔离上下文│
    └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
         │             │             │             │
    ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐  ┌────▼─────┐
    │Scratchpad│  │ Tool RAG │  │ 摘要压缩  │  │ 多 Agent │
    │ 结构化笔记│  │ 按意图筛选│  │ 递归摘要  │  │ 各自独立 │
    │          │  │ Tool     │  │ 上下文窗口│  │ 上下文窗口│
    │Memory    │  │ 注册表   │  │ 滑动窗口  │  │          │
    │ 跨会话记忆│  │          │  │ 裁剪     │  │ State    │
    └──────────┘  └──────────┘  └──────────┘  │ 显式字段 │
                                               └──────────┘
```

### 演进路线（四步走）

```
 Step 0 (当前)        Step 1 (近期)        Step 2 (中期)         Step 3 (远期)
 ───────────         ───────────         ───────────          ───────────
 Prompt Stuffing     Tool RAG            Progressive          Scratchpad +
 全量注入 10 Tool    意图预筛 + 精准注入  Disclosure           Memory Store
                     + 对话压缩           按需加载 Tool
 ~30K tokens         ~10K tokens          ~4K tokens           ~2K tokens
 弱模型精度↓         弱模型精度↑↑         成本↓↓               多会话连续性

┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ System Prompt  │  │ System Prompt  │  │ System Prompt  │  │ System Prompt  │
│ ├ base.j2      │  │ ├ base.j2      │  │ ├ base.j2(精简)│  │ ├ base.j2      │
│ ├ 10 Tool 描述 │  │ ├ Tool 注册表  │  │ ├ Skill 索引   │  │ ├ Skill 索引   │
│ │  (全量)      │  │ │ (name+触发词)│  │ │ (name only) │  │ └ 用户画像     │
│ └ 用户信息     │  │ ├ 压缩历史     │  │ └ 用户画像     │  │                │
│                │  │ └ 筛选后 Tool  │  │                │  │ + Scratchpad   │
│ = ~30K tokens  │  │   (2-3个)      │  │ = ~4K tokens   │  │   结构化笔记    │
│ 精度↓ 成本↑    │  │ = ~10K tokens  │  │ 精度↑ 成本↓↓   │  │ + Memory       │
└────────────────┘  │ 精度↑↑ 成本→  │  └────────────────┘  │   跨会话记忆    │
                    └────────────────┘                       │ = ~2K tokens   │
                                                             │ 连续性↑↑      │
                                                             └────────────────┘
```

### Step 0 → Step 1: Tool RAG（已部分实施）

> 论文 [ToolRAG](https://arxiv.org/abs/2410.14594) 显示：按语义相似度预筛 Tool 后再注入，tool selection 准确率提升 3 倍。

**当前已实施:**
- [x] 10 个 Skill description 优化为"意图场景描述"格式
- [x] system prompt 注入【可用工具】映射表（name → 触发关键词）
- [x] directive 格式强化 tool 调用指令（"用户说X → 必须调用Y"）

**待实施 — Tool RAG 预筛选:**

```python
# graph.py 新增 tool_selector 模块

def select_tools_by_intent(user_message: str, all_tools: list, top_k: int = 3) -> list:
    """根据用户消息意图，预筛选最相关的 top_k 个 Tool。

    策略: 关键词匹配优先（零成本），语义相似度兜底（embedding）。
    """
    # 1. 关键词匹配: 从 Tool description 提取触发词表
    scored = []
    for tool in all_tools:
        score = _keyword_match_score(user_message, tool.description)
        scored.append((tool, score))

    # 2. 如果 top_k 内有关键词命中，直接返回
    top = sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]
    if top[0][1] > 0:
        return [t for t, s in top if s > 0]

    # 3. 兜底: embedding 语义相似度（可选，Phase 4）
    return all_tools  # 未命中则全量注入
```

**效果预期:**
- 弱模型 (qwen3.6-flash) 只需从 2-3 个候选 Tool 中选择 → 准确率大幅提升
- System prompt 注入注册表 + 精简 Tool 列表 → token 消耗降低 60%+
- 消除 "Context Distraction"（10 个 Tool 的重叠描述导致模型混淆）

### Step 1 各子策略对照

| 策略 | 方法 | 适用场景 | 成本 |
|------|------|---------|------|
| **Keyword Pre-filter** | 用户消息 → 触发词表匹配 → 候选 Tool | 当前首选，零额外 API 调用 | O(1) |
| **Tool Registration Table** | System prompt 列出 tool_name → 关键词映射 | 已实施，配合 Keyword Pre-filter | ~200 tokens |
| **Embedding RAG** | 用户消息 embedding → Tool description embedding 余弦相似度 | Keyword 未命中时的兜底 | ~50ms + embedding API |
| **LLM 路由** | 用更小模型做意图分类 → 选择 Tool | 精度最高但成本高 | 1次额外 LLM 调用 |

### Step 2: Progressive Disclosure

> 当 Tool 数量增长到 20+ 时，即使预筛选也有压力。按需加载完整 Tool schema。

```
用户消息 → 意图识别 → Skill 索引(name+触发词, ~80 tokens/skill)
                         │
                         ├─ 命中 → 加载完整 Tool schema + description
                         │         注入 bind_tools()
                         │
                         └─ 未命中 → 纯对话模式，不注入任何 Tool
```

**关键设计:**
- Skill 索引常驻 system prompt（名称 + 1行触发词，~800 tokens / 10 skills）
- 完整 Tool schema 仅在命中时动态注入 `bind_tools()`
- LangGraph 的 `ToolNode` 已支持动态 tool 列表

### Step 3: Scratchpad + Memory Store

> 跨会话连续性 + 结构化工作记忆

```
┌───────────────────────────────────────────────────┐
│                 上下文工程完整架构                    │
│                                                    │
│  ┌─────────────┐     ┌──────────────┐             │
│  │  Scratchpad  │     │ Memory Store │             │
│  │  (会话内)    │     │  (跨会话)    │             │
│  │  ├ 当前任务  │     │  ├ 用户偏好  │             │
│  │  ├ 已选Tool │     │  ├ 历史摘要  │             │
│  │  ├ 中间结果  │     │  ├ 操作模式  │             │
│  │  └ 待确认项  │     │  └ 作物日历  │             │
│  └──────┬──────┘     └──────┬───────┘             │
│         │                   │                      │
│         ▼                   ▼                      │
│  ┌──────────────────────────────────────────┐     │
│  │           Context Assembler              │     │
│  │  ├ base.j2 (精简 system prompt)          │     │
│  │  ├ Skill 索引 (name + 触发词)            │     │
│  │  ├ Scratchpad 片段 (当前任务相关)         │     │
│  │  ├ Memory 检索结果 (用户偏好/历史)        │     │
│  │  ├ 压缩后的对话历史 (sliding window)      │     │
│  │  └ 动态筛选的 Tool (2-3个)               │     │
│  └──────────────────────────────────────────┘     │
│                    │                               │
│                    ▼                               │
│              LLM (qwen3.6-flash)                   │
│                                                    │
│  目标: ~2K tokens 稳态，95%+ Skill 命中率          │
└───────────────────────────────────────────────────┘
```

### 实施时间表

| 阶段 | 方案 | 核心模块 | 效果 | 实施时机 |
|------|------|---------|------|---------|
| Step 0 | Description 优化 + Prompt 映射表 | `skills/*/main.py` + `base.j2` | ✅ 已完成 | 当前 |
| Step 1a | Keyword Pre-filter | `agent/tool_selector.py` | 候选 Tool 2-3个 | Phase 3 FC 稳定后 |
| Step 1b | Sliding Window + 摘要压缩 | `agent/history_compressor.py` | 历史 ~70% 压缩 | Phase 3 后 |
| Step 2 | Progressive Disclosure | `agent/context_assembler.py` | Prompt ~90% 瘦身 | Tool 数量 >15 时 |
| Step 3 | Scratchpad + Memory | `agent/scratchpad.py` + `agent/memory_store.py` | 多会话连续性 | Phase 4 智能化 |

---

## 六、技术栈演进

```
                    当前                              目标
                    ────                              ────
后端框架    FastAPI 0.115                    FastAPI (保持)
LLM         DashScope (Qwen)                 DashScope + 可选多模型
Agent       LangGraph 0.2                    LangGraph (升级)
数据库      SQLite (默认模式)                  SQLite WAL → PostgreSQL*
认证        无                                JWT (PyJWT)
缓存        内存 (skill_cache)                 内存 + 可选 Redis*
观测        LangSmith + 自建 trace             保持 + 增强
前端        React+TS+Vite (Admin)              + React Native (农户端)
Skill引擎   skillify-sdk (自有)                skillify-sdk (持续迭代)

* 根据用户规模决定，SQLite WAL 足以支撑 ~100 并发
```

---

## 七、关键度量

| 度量 | 当前值 | Phase 3 目标 | Phase 5 目标 |
|------|--------|-------------|-------------|
| 并发用户 | 1 | 5-10 | 100+ |
| Agent 响应延迟 | ~3s | ~2s | <1.5s |
| Skill 命中率 | ~75% (FC+描述优化后) | ~90% (Tool RAG) | ~95% |
| 多轮对话连贯性 | 无 | 3轮上下文 | 10轮+摘要 |
| Prompt token 消耗 | ~30K/轮 | ~10K/轮 (Tool RAG) | ~4K/轮 (Progressive) |
| 测试覆盖率 | 部分 | >80% | >90% |
| 部署频率 | 手动 | 手动 | CI/CD 自动 |

---

## 八、风险与缓解

| 风险 | 影响 | 缓解策略 |
|------|------|---------|
| import 路径迁移遗漏 | 运行时 ImportError | 全量测试 + ruff 检查 + grep 残留扫描 |
| 数据库迁移失败 | 数据丢失 | 迁移前热备 + 回滚脚本 |
| JWT 密钥泄露 | 安全漏洞 | 环境变量注入 + 密钥轮换 |
| LLM API 变更/限流 | 服务中断 | 多模型 fallback + 熔断器 |
| 用户增长超 SQLite 承载 | 性能瓶颈 | WAL 模式 + 预留 PostgreSQL 迁移路径 |
| Prompt 注入攻击 | 数据泄露 | Guardrails 输入过滤 + 输出校验 |

---

## 九、里程碑总览

```
2026-05 ─── Phase 1: 架构清理 ────────────────── 目标: 1周内
  │
2026-06 ─── Phase 2: 多用户 + 数据安全 ───────── 目标: 2周内
  │
2026-06 ─── Phase 3: 功能增强 ────────────────── 目标: 4周内
  │         ├── Dual Weather
  │         ├── Session & Context
  │         └── Function Calling
  │
2026-07 ─── Phase 4: 智能化 ──────────────────── 目标: 2月内
  │         ├── RLHF 循环
  │         ├── Prompt 优化
  │         └── 个性化记忆
  │
2026-08 ─── Phase 5: 规模化 ──────────────────── 目标: 3月内
            ├── 移动端 App
            ├── 容器化部署
            └── PostgreSQL (按需)
```
