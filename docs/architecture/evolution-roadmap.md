---
last_updated: 2026-06-04
status: active
---

# Farm-Manager 系统演进路线图

> 全局视角：从当前状态到目标架构的分阶段演进计划。

---

## 一、当前架构全貌（2026-06）

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户端                                    │
│              React Native App / Admin Web                        │
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
│                   FastAPI 后端                                   │
│                                                                  │
│  bootstrap/                    api/                              │
│  ├── app_factory/routes        ├── agent/auth/admin              │
│  └── middleware/lifespan       ├── cost/crop/cycle/log/debt      │
│                                └── weather/settings/feedback     │
│                                                                  │
│  agent/                        context/ memory/ prompt/          │
│  ├── application               ├── ContextBundle/selector        │
│  ├── runtime/planner/executor  ├── MemoryService/observation     │
│  ├── response/sessions         └── Prompt composer/renderer      │
│  └── skills                    services/ modules/                │
│                                                                  │
│  infra/ core/                  evaluation/ simulation/            │
│  ├── trace/limiter/cache       ├── replay/metrics/report          │
│  ├── pending/circuit breaker   └── Agent 仿真回归                 │
│  └── config/database/logger                                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      MySQL 8.x (生产) / SQLite (兼容开发)          │
│  farms | crops | cycles | costs | cost_categories | logs         │
│  conversations | conversation_messages | trace_records           │
│  token_stats | guardrails_logs | idempotency_keys | agents       │
└─────────────────────────────────────────────────────────────────┘

外部依赖: 多 LLM Provider | QWeather | Open-Meteo | LangSmith(可选观测)
```

### 2026-06-03 数据库迁移完成

- 生产数据库已从 SQLite 迁移到 MySQL 8.x。
- 后端通过 Alembic 管理 schema，启动时执行 `alembic upgrade head`。
- 开发环境仍保留 SQLite 兼容能力，通过 `database.url` 切换。
- SQLite 到 MySQL 全量迁移校验通过：20 张业务表，768 行数据。

---

## 二、已规划变更与落地状态

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
   │  和风天气+OpenMeteo│ │  对话管理       │ │  (持续演进)      │
   │  预警爬虫        │ │  多轮上下文注入  │ │  上下文压缩      │
   │  API Key 统一管理│ │  用户信息注入    │ │  渐进式加载      │
   └─────────────────┘ └─────────────────┘ └──────────────────┘
```

### 执行状态

| 优先级 | Change | 当前状态 | 后续关注 |
|-------|--------|---------|------|
| P0 | ① Architecture Cleanup | 已部分落地：bootstrap、agent runtime、prompt/context/memory 边界已出现 | 清理兼容入口，继续迁移 `services/` |
| P0 | ② Storage Redesign | 已落地多用户、JWT、MySQL 迁移、token 配额基础 | 完善模块边界和管理端能力 |
| P1 | ③ Dual Weather | 已落地 QWeather/Open-Meteo 策略和预警注入 | 继续补齐稳定性和城市覆盖测试 |
| P1 | ④ Session & Context | 已落地会话、ContextBuilder、Memory observation 骨架 | 收敛 runtime 对 context 的直接构建 |
| P2 | ⑤ Context Engineering | 已进入工程化阶段：selector、budget、cache、memory | 增强长期记忆、检索和评测闭环 |
| P2 | ⑥ Agent 数据飞轮 | 已落地 DataFlywheel 页面、事件同步、标注、case draft 基础 | 演进到规则候选、LLM 预标注、人工确认、仿真回归和训练数据出口闭环 |

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

### Phase 1: 架构清理（已部分落地，持续收敛）

> 目标：消除技术债，为所有后续工作铺路

```
旧状态                                当前状态
─────────                             ──────────────
core/ (19个模块混在一起)               core/ (7个基础模块)
                                      agent/ (Agent领域)
                                      infra/ (可观测性)

app/agents/ (旧名)                    app/agent/ (已重命名)
_DEFAULT_PROMPTS (双数据源)           prompts/*.j2 (单一数据源)
term_whitelist.py (死代码)            已删除
farm_id=1 硬编码                      user_id → farm_id 动态解析
```

**关键交付物:**
- [x] OpenSpec 提案: `backend-architecture-cleanup`
- [x] `bootstrap/`、`agent/runtime/`、`prompt/`、`context/`、`memory/` 初步落地
- [ ] 清理剩余兼容入口并保持 import 路径零残留

---

### Phase 2: 多用户 + 数据安全（主体已落地）

> 目标：支持多用户登录，数据隔离，生产级数据库配置

```
旧状态                                当前状态
─────────                             ──────────────
无认证                                JWT 认证
farm_id=1 硬编码                       user_id → farm_id 动态
SQLite 默认模式                        MySQL 8.x + Alembic
单用户                                多用户隔离
无反馈收集                             feedback_records 表
advice + report 分开                   agent_records + conversations
```

**关键交付物:**
- [x] OpenSpec 提案: `storage-redesign-multi-user`
- [x] 用户注册/登录接口 + JWT 依赖
- [x] SQLite → MySQL 迁移脚本和 Alembic schema 管理
- [ ] 继续完善运维备份和回滚流程

---

### Phase 3: 功能增强（主体已落地，继续增强）

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
└── Tool Pre-Filter / Tool Selection
    ├── Keyword Pre-filter 模块
    ├── 候选 Tool 2-3 个精准注入
    └── 弱模型 tool selection 准确率提升
```

**关键交付物:**
- [x] OpenSpec 提案: `dual-weather-provider`
- [x] OpenSpec 提案: `session-management-and-context-injection`
- [x] Function Calling 迁移 (`function-calling-migration`)
- [x] Tool Selection Fix (`fc-tool-selection-fix`)
- [x] Dual Weather Provider 主体实现
- [x] Session & Context 主体实现
- [x] Tool Pre-Filter / Tool Selection 主体实现
- [ ] 长期记忆检索和评测闭环

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
| Agent 数据飞轮 | 真实会话和仿真失败进入 DataFlywheel，经规则候选、LLM 预标注、人工确认后输出回归和训练数据 | Session event log、Trace、Simulation、Evaluation |
| RLHF/偏好数据循环 | 利用人工确认的好坏样本、纠正回复和 pairwise 对比评估 Prompt 质量 | DataFlywheel 标签和数据集版本 |
| Prompt A/B 测试 | 同一意图多版本 Prompt，按效果自动切换 | RLHF 数据 |
| 个性化记忆 | 会话 running summary 已落地；用户偏好、历史操作模式等长期记忆后续独立推进 | Phase 2 多用户 |
| 多 Agent 协作 | 种植顾问 + 气象分析师 + 财务顾问 分工 | Function Calling 稳定 |
| 知识库 (RAG) | 作物种植指南、病虫害图谱 → 检索增强 | 知识库数据源 |

Agent 数据飞轮按 [agent-data-flywheel-industrial-roadmap.md](/Users/ljn/Documents/demo/explore/docs/architecture/agent-data-flywheel-industrial-roadmap.md) 推进。完成态是：

```text
真实会话 / Playground / Simulation 失败
  → MySQL 热索引 + JSONL 原始事件
  → 规则初筛
  → LLM 自动预标注
  → 人工确认和根因标注
  → Bad Case / Tool Selection / Pending Safety / SFT 数据集
  → Simulation / Evaluation 回归验证
  → 修 prompt / router / skill / pending plan
```

阶段目标：

- P0：证据完整化，确保每轮对话能导出 debug JSON 并回溯 trace、tool、pending lifecycle。
- P1：人工标注闭环，支持固定标签、备注、规则候选、case draft 和当前样本 JSONL 导出。
- P2：AI 自动预标注，引入 `llm_judge` 建议标签、置信度、根因和采纳/驳回工作流。
- P3：Dataset 与仿真评测闭环，支持数据集版本、DB-backed simulation cases、失败回流和趋势评分。
- P4：训练与调优出口，导出 SFT、router、pending safety 和 prompt regression 数据。

---

### Phase 5: 规模化 (2-3月)

> 目标：移动端上线，用户增长，系统稳定运行

```
Phase 4 完成后                        Phase 5 目标
─────────                             ──────────────
Admin Web + React Native              微信小程序 / 更多轻量入口
MySQL 8.x / SQLite 兼容                按规模评估数据库演进
单机部署                              容器化 + CI/CD
中文仅                                多语言 (可选)
```

**规划方向:**

| 方向 | 描述 | 触发条件 |
|------|------|---------|
| 移动端 App | React Native 农户端 | 持续迭代 |
| 微信小程序 | 轻量入口，分享传播 | App 稳定后 |
| 数据库演进 | MySQL 连接池、备份、必要时迁移 PostgreSQL | 并发和运维复杂度上升 |
| 容器化 | Docker + docker-compose | 部署需求 |
| CI/CD | GitHub Actions 测试+部署 | 团队协作需求 |

---

## 五、上下文工程演进路径

> 基于 Lance Martin (LangChain) 上下文工程四维框架：**Write / Select / Compress / Isolate**
> 参考: [Context Engineering for Agents](https://rlancemartin.github.io/2025/06/23/context_engineering/) | [12-Factor Agents](https://github.com/humanlayer/12-factor-agents/blob/main/content/factor-03-own-your-context-window.md)
>
> Spike 验证：两层规则匹配（regex + keyword）在 34 个用例上达到 100% 召回率，0.005ms/次

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

### Step 0 → Step 1: Tool Pre-Filter（已部分实施）

> Spike 验证：两层规则匹配（写操作 regex + 查询操作 keyword），34 用例 100% 召回率。

**当前已实施:**
- [x] 10 个 Skill description 优化为"意图场景描述"格式
- [x] system prompt 注入【可用工具】映射表（name → 触发关键词）
- [x] directive 格式强化 tool 调用指令

**已实施主体，后续持续调优 — Tool Pre-Filter:**

```python
# agent/tool_selector.py

# Layer 1: 写操作 Regex（deterministic，100% 召回）
WRITE_PATTERNS = {
    "create_cost_record": [
        r"(买了|卖了|花了|收入|支出|赊账|记账|记一笔|付了|收了)",
        r"\d+\s*(元|块|万|w|W|千|百)",
    ],
    "settle_debt": [
        r"(还[了钱账给]|清账|结清|欠款|还款)",
        r"(账[结清]|结了.*账|欠.*结)",
    ],
    # ...
}

# Layer 2: 查询操作 Keyword（~95% 召回）
QUERY_TRIGGERS = {
    "get_weather_forecast": {"天气", "预报", "降雨", "温度", "雨"},
    "get_cost_summary": {"余额", "收支", "成本", "利润", "月额"},
    # ...
}

def select_tools(user_message, all_tools, top_k=3):
    candidates = regex_match(user_message) | keyword_match(user_message)
    return candidates if candidates else all_tools  # fallback
```

**效果预期:**
- 写操作 tool selection → 100%（regex deterministic）
- 查询操作 tool selection → ~95%（keyword matching）
- 总体 token 消耗降低 60-80%（候选 1-3 个 vs 全量 10 个）

### Step 1 各子策略对照

| 策略 | 方法 | 适用场景 | 成本 |
|------|------|---------|------|
| **Regex 模式匹配** | 写操作 Tool 维护 regex pattern 列表 | 记账/还账/建茬口等确定性操作 | O(1) deterministic |
| **Keyword 匹配** | 查询 Tool 维护策划触发词表 | 天气/余额/趋势等模糊查询 | O(1) |
| **Fallback** | 无命中时全量注入 | 歧义输入、边界 case | 不劣于现状 |
| **Embedding RAG** | 用户消息 embedding → Tool description 余弦相似度 | Phase 4 可选扩展，Tool >20 时 | ~50ms + API |

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
| Step 1 | Tool Pre-Filter (regex+keyword) | `agent/tool_selector.py` | 写操作100%, 查询~95% | 已实施主体，持续调优 |
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
数据库      MySQL 8.x / SQLite 兼容            视规模评估 PostgreSQL*
认证        JWT                               JWT + 权限策略增强
缓存        内存 (skill_cache)                 内存 + 可选 Redis*
观测        LangSmith + 自建 trace             保持 + 增强
前端        React+TS+Vite (Admin)              + React Native (农户端)
Skill引擎   skillify-sdk (自有)                skillify-sdk (持续迭代)

* 根据用户规模和运维要求决定是否继续迁移数据库。
```

---

## 七、关键度量

| 度量 | 当前值 | Phase 3 目标 | Phase 5 目标 |
|------|--------|-------------|-------------|
| 并发用户 | 1 | 5-10 | 100+ |
| Agent 响应延迟 | ~3s | ~2s | <1.5s |
| Skill 命中率 | ~75% (FC+描述优化后) | ~90% (Tool RAG) | ~95% |
| 多轮对话连贯性 | 已有会话上下文 | 3轮上下文 | 10轮+摘要 |
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
| 用户增长超单机数据库承载 | 性能瓶颈 | 连接池、缓存、备份和数据库迁移预案 |
| Prompt 注入攻击 | 数据泄露 | Guardrails 输入过滤 + 输出校验 |

---

## 九、里程碑总览

```
2026-05 ─── Phase 1: 架构清理 ────────────────── 已部分落地
  │
2026-06 ─── Phase 2: 多用户 + 数据安全 ───────── 主体已落地
  │
2026-06 ─── Phase 3: 功能增强 ────────────────── 主体已落地，继续增强
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
