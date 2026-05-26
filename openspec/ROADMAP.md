# 开发路线图

## 已完成（已归档）

| # | Change | 状态 |
|---|--------|------|
| 0 | prompt-governance | done |
| 0 | skill-engine-with-cache-and-circuit-breaker | done |
| 0 | robustness-and-admin-completeness | done |
| 0 | mobile-four-tab-redesign | done |
| 0 | farmer-first-agent | done |

## 已实施（代码已提交，待归档）

| # | Change | 内容 | 关键提交 |
|---|--------|------|----------|
| 1 | farm-context-aware-agent | 结构化赊账数据模型 + /debts API + 作物模板自定义 + 赊账管理页面 | cost_records 字段扩展, /debts CRUD, /crops/templates, 移动端赊账页 |

## 待实施（按优先级排序）

### P0: enable-function-calling

**为什么先做**: 当前模型 `qwen-flash-character` 不支持 Function Calling，LangGraph 的 skill 执行机制完全失效。已实现的 6 个写操作 Skill 全部静默失败——没有 FC，后面所有 skill 改造都没有意义。

**核心改动**:
- 切换模型 `qwen-flash-character` → `qwen3.6-flash` + `enable_thinking=false`
- `AIConfig` 新增 `enable_thinking: bool = False`
- `get_llm()` 传递 `model_kwargs`
- `base.j2` 新增 FC 硬约束（禁止编造实时数据）
- 不使用 `tool_choice="required"`（破坏闲聊）

**依赖**: 无

---

### P1: farm-context-aware-agent（结构化赊账 + 作物模板 + 多作物建议）

**为什么第二个**: `farmer-first-agent` 已完成 Agent 层的"对话式赊账"（通过 note 文本识别）和上下文注入。但父母需要的是**结构化数据层**和**独立管理页面**：能独立查看"我欠谁多少钱"、能自己添加辣椒/小瓜模板、记账时能选"赊账"类型。这些是农场 app 的核心功能缺失。

**核心改动**:
- 结构化赊账：`cost_records` 新增 `record_subtype`/`counterparty`/`due_date`/`settled_at`/`parent_record_id` 字段，替代 note 文本识别方案
- 赊账 API：新增 `/debts` 系列端点（查询、统计、还款）
- 作物模板自定义：`POST/PUT/DELETE /crops/templates`，用户可自由创建（替代硬编码西瓜+豆角）
- 多茬口建议完善：确认 `/agent/daily` 在无 `cycle_id` 时按 active 茬口分别生成建议，缓存键包含茬口列表
- 移动端：记账页增加"赊账"类型、新增"赊账管理"页、新增"作物模板"页

**依赖**: enable-function-calling（FC 跑通后现有 Skill 才能执行）; farmer-first-agent（Agent 层已完成，本 change 专注数据层+展示层）

---

### P2: session-management-and-context-injection

**为什么第三个**: 核心功能（记账、建茬口、赊账）就位后，用户体验的下一个瓶颈是多轮对话——用户无法追问（如"后天呢"）。同时 `<user_context>` 注入让天气 skill 获得城市信息，为 P3 天气 provider 铺路。

**核心改动**:
- 新增 `Conversation` + `ConversationMessage` 数据模型
- `ChatRequest` 新增 `session_id`
- 单会话模式（24h 自动过期，10 轮历史注入）
- `base.j2` 新增 `<user_context>` XML 段（城市/称呼/季节）
- 前端生成 session_id，后端 lazy creation

**依赖**: enable-function-calling

---

### P3: dual-weather-provider

**为什么最后**: 多轮对话 + 用户上下文就位后，天气 skill 才能根据 `<user_context>` 中的城市正确路由 provider。SecretsConfig 统一密钥管理可复用 P1/P2 的配置体系。

**核心改动**:
- `SecretsConfig` 统一 API key 管理（dashscope/qweather/langsmith）
- Weather Provider Strategy（和风天气 + Open-Meteo + 自动兜底）
- 中国天气网预警爬虫（免费，不消耗和风配额）
- 新增 `get_air_quality` skill
- 和风天气：预报 + 生活指数 + AQI
- Open-Meteo：全球预报 + 空气质量兜底

**依赖**: session-management-and-context-injection（`<user_context>` 提供城市信息）

---

## 依赖关系

```
enable-function-calling (P0)
        │
        ├──────────────────┐
        ▼                  ▼
farm-context-aware-agent (P1)    session-management (P2)
                                     │
                                     ▼
                              dual-weather-provider (P3)
```

P1 和 P2 可以并行实施（无互相依赖），但都依赖 P0。P3 依赖 P2。

## 各 Change 规模估算

| Change | 改动文件数 | 核心模块 | 风险 |
|--------|-----------|---------|------|
| enable-function-calling | ~5 | config.py, llm.py, graph.py, base.j2 | 低（模型切换） |
| farm-context-aware-agent | ~15 | DB迁移, /debts API, /crops/templates, 赊账管理页, 作物模板页 | 中（数据模型变更） |
| session-management-and-context-injection | ~10 | 新增2模型, advisor.py, graph.py, base.j2 | 中（DB迁移） |
| dual-weather-provider | ~12 | weather_service拆分, 新provider, config重构 | 中（密钥迁移） |
