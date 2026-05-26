# 开发路线图

## 已完成（已归档）

| # | Change | 状态 |
|---|--------|------|
| 0 | prompt-governance | done |
| 0 | skill-engine-with-cache-and-circuit-breaker | done |
| 0 | robustness-and-admin-completeness | done |
| 0 | mobile-four-tab-redesign | done |

## 已实施（代码已提交，待归档）

| # | Change | 内容 | 关键提交 |
|---|--------|------|----------|
| 1 | farmer-first-agent | 上下文注入 + 短回复 + 6个写操作 Skill + 确认机制 | farm_context_service, prompt模板改造, 记账/建茬口/记农事/还赊账/更新阶段, pending action |
| 2 | farm-context-aware-agent | 上下文感知 + display_name + 上下文摘要组装 | display_name, farm_context_service 改造, 摘要注入 |

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

### P1: farm-context-aware-agent（赊账 + 多茬口 + 作物模板）

**为什么第二个**: FC 跑通后，已实现的写操作 Skill 才能真正工作。但当前系统还缺关键能力：赊账管理（父母刚需）、多茬口并行感知、用户自定义作物模板。这些都是农场 app 的核心功能缺失，比多轮对话更影响用户留存。

**核心改动**:
- 赊账管理：`cost_records` 新增 subtype/counterparty/due_date 字段，新增 `/debts` API + 还款流程
- 多茬口感知：`cycle_service.get_active_cycles()` + 多作物每日建议
- 作物模板管理：`POST/PUT/DELETE /crops/templates`，用户可自定义（替代硬编码西瓜+豆角）
- 上下文注入增强：摘要中包含赊账信息、多茬口状态
- 移动端：赊账录入页、赊账管理页、作物模板页、多作物建议卡片

**依赖**: enable-function-calling（FC 跑通后 Skill 才能执行）

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
| farm-context-aware-agent | ~20 | DB迁移, 赊账API, 多茬口, 作物模板, 移动端 | 高（多模块） |
| session-management-and-context-injection | ~10 | 新增2模型, advisor.py, graph.py, base.j2 | 中（DB迁移） |
| dual-weather-provider | ~12 | weather_service拆分, 新provider, config重构 | 中（密钥迁移） |
