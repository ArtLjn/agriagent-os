## Why

当前 Agent 的每日建议和对话回复是「通用型」的——system prompt 硬编码"擅长西瓜、豆角"，Agent 不知道用户农场当前实际在种什么作物、处于哪个生长阶段、有没有赊账待还。这导致春季只种西瓜的用户收到了豆角的种植建议，严重降低信任度。同时，农业中普遍存在的赊账（向农资店赊购、雇工赊工资、买家赊货款）完全没有被系统记录，用户需要额外用本子记账。

父母作为真实用户，需要的是一个「越用越懂我」的 Agent：知道我棚里现在是什么、欠谁多少钱、上周做了什么、下周该注意什么。

## What Changes

- **新增赊账管理模块**：在成本记账中引入 `debt`（应付）和 `receivable`（应收）两种记录类型，支持记录债权人/债务人、约定还款日期、还款状态。
- **新增多茬口并行感知**：改造每日建议生成逻辑，自动查询农场所有 `active` 状态的茬口，按作物分别生成建议，而非混为一谈。
- **新增 Agent 上下文注入**：在 Agent 调用前自动组装「农场现状摘要」（当前茬口、近期农事、成本概况、应收应付、未来天气），作为 system prompt 的一部分注入。
- **改造作物模板管理**：从"固定西瓜+豆角"改为用户可自由创建作物模板（支持小瓜、辣椒等），每个模板含生长阶段定义。
- **移动端新增赊账录入入口**：在记账页面增加"赊账"类型，区分"我欠别人"和"别人欠我"。
- **改造每日建议 API**：`/agent/daily` 支持按农场维度查询（不传 cycle_id 时自动汇总所有 active 茬口）。

## Capabilities

### New Capabilities

- `debt-management`: 赊账/应收应付的全生命周期管理（创建、还款、查询、逾期提醒）
- `multi-cycle-awareness`: 多茬口并行状态跟踪与 Agent 感知
- `agent-context-injection`: Agent 调用前的结构化上下文自动组装与注入
- `crop-template-management`: 用户自定义作物模板（替代硬编码西瓜+豆角）

### Modified Capabilities

- `daily-advice-cache`: 每日建议的生成逻辑从"通用建议"改为"基于实际 active 茬口的定制化建议"，prompt 中注入农场上下文摘要
- `user-settings`: 新增 `default_crop_templates` 和 `active_cycles` 偏好字段（移动端设置页管理）

## Impact

- **后端**：新增 `DebtRecord` 模型、`CropTemplate` CRUD 扩展、`CycleService` 查询逻辑改造、`AgentService` 上下文组装逻辑
- **API**：新增 `/debts` 系列端点，改造 `/agent/daily`（支持无 cycle_id 模式），`/cycles` 增加活跃茬口查询参数
- **数据库**：新增 `debt_records` 表，扩展 `crop_templates` 和 `cost_records` 字段
- **移动端**：记账页面增加赊账类型，新增"我的农场"作物管理入口，每日建议页展示多作物建议卡片
- **Agent Prompt**：`base.j2` 模板中增加 `{{ farm_context_summary }}` 变量占位符（依赖 prompt-governance 完成后接入）
