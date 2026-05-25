## Context

Farm Manager 移动端（React Native + Zustand）有四个底部 Tab：首页、AI助手、记账、我的。当前存在成本和体验问题：首页每日农事建议每次打开 app 都触发完整 LLM 调用（含多步 tool_calls），无缓存机制；"我的"页面放的是 AI 功能快捷入口而非用户设置；报告页无 Markdown 渲染且无历史记录。

后端技术栈：FastAPI + LangGraph + skillify SDK（Skill 系统）+ SQLite。LLM 使用阿里云 DashScope Qwen 模型。

## Goals / Non-Goals

**Goals:**
- 每日建议 API 调用从 N次/天 降为 1次/天/城市，缓存命中时 0 token 消耗
- AI 助手 Tab 从"纯聊天"变为"AI 功能中心"（对话 + 报告历史）
- "我的"页面聚焦用户设置（农场/偏好/通知/数据），预留登录体系
- 报告内容正确渲染 Markdown
- 首页信息密度经设计，一屏内看到最关键信息

**Non-Goals:**
- 不实现真实的用户认证/登录（仅预留 UI 扩展点）
- 不实现推送通知（仅预留设置开关 UI）
- 不改动记账 Tab
- 不改动后端 LangGraph 图结构

## Decisions

### D1: 每日建议缓存 — 后端 DB 缓存（非 Redis）

**选择**: 在 SQLite 中新建 `advice_cache` 表，按 `farm_id + date + city` 唯一索引缓存。

**备选方案**:
- 前端 AsyncStorage 缓存：简单但无法跨设备同步，且无法区分"今天第一次"还是"已缓存"
- Redis 缓存：过度工程，当前单实例 SQLite 足够

**理由**: 后端缓存可精确控制过期策略（按自然天），切换城市时自动失效（city 变了 key 就变了），且与现有 SQLite 基础设施一致。

### D2: 报告历史 — 复用现有 report 表

**选择**: 后端已有 `generateReport` 写入报告记录的逻辑，新增 `GET /agent/reports` 列表接口即可。

**理由**: 报告数据已经在后端生成并存入 DB，只需暴露查询接口，无需新建表。

### D3: AI 助手 SegmentedControl — 前端 Tab 切换

**选择**: 在 AgentChatScreen 顶部加 `对话 | 报告` SegmentedControl，两个视图在同一 Screen 内切换（不新增导航路由）。

**备选方案**:
- 新增底部第 5 个 Tab：5 个 Tab 在移动端偏多，且报告是低频功能
- Stack Navigator 嵌套：增加导航复杂度

**理由**: 单 Screen 内状态管理简单，避免导航层级加深，用户在对话和报告间切换零延迟。

### D4: "我的"页面 — 分区卡片式布局

**选择**: 按"用户信息 → 农场设置 → 种植偏好 → 通知 → 数据 → 关于"分区，每区一个 Card 组件。

**理由**: 符合 iOS/Android 原生设置页的分组列表习惯，分区清晰可扩展。

## Risks / Trade-offs

- **[缓存时效性]** → 缓存后用户可能看到"旧"建议（如天气突变）。缓解：提供刷新按钮，切换城市自动失效
- **[advice_cache 表体积]** → 每个农场每天每城市一条记录，长期增长。缓解：添加定期清理任务（保留最近 30 天）
- **[SegmentedControl 学习成本]** → 用户可能不知道报告功能在 AI 助手里。缓解：首页快捷操作"生成报告"仍跳转到 AI 助手的报告视图
- **[预留 UI 的空状态]** → 登录/通知等预留项点击后无功能。缓解：显示"即将上线"提示
