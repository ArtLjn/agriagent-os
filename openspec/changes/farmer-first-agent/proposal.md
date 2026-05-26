## Why

当前 Agent 回复「不认识用户」——prompt 里只有时间，不知道用户种什么、欠谁钱、天气咋样，导致建议泛泛而谈。同时回复长篇大论（300-500字），农户看到第一行就关了。更关键的是，Agent 只能「查」不能「做」，农户想记一笔账、建个茬口还得退出对话去表单操作，体验割裂。

需要让 Agent 做到三点：**认识用户**（注入农场上下文）、**说到心里**（短而准的回复）、**帮用户干活**（通过 Skill 执行写操作）。

## What Changes

- **新增农场上下文注入**：Agent 调用前自动查询数据库组装「农场现状摘要」（茬口、农事、债务、天气），注入 `{{ farm_context_summary }}`，取代当前的纯时间注入
- **新增回复格式约束**：在 base.j2 中增加硬性格式规则（每条≤2行、总共≤5条、先结论后原因、口语化），控制 Agent 输出长度
- **新增用户称呼机制**：从用户设置中读取称呼（昵称/名字），Agent 回复时使用，替代「您好」
- **新增写操作 Skill**：将记账、建茬口、记农事、还赊账等业务操作封装为 Skill，Agent 通过对话即可执行
- **改造每日建议返回格式**：从纯文本改为结构化 JSON（列表卡片），前端用独立卡片渲染每条建议
- **改造聊天确认流程**：写操作 Skill 执行前先向用户确认参数，确认后才执行

## Capabilities

### New Capabilities

- `farm-context-injection`: Agent 调用前自动组装农场现状摘要（茬口/农事/债务/天气）并注入 prompt，作为独立的 farm_context_service 层，方便以后扩展 RAG 或 MySQL
- `agent-response-format`: Agent 回复格式控制——短句式、条目化、口语化、用户称呼，覆盖每日建议和聊天两个场景
- `action-skills`: 写操作 Skill 集合——记账(create_cost_record)、建茬口(create_crop_cycle)、记农事(log_farm_activity)、还赊账(settle_debt)、更新阶段(update_crop_stage)，含参数提取和确认流程
- `structured-daily-advice`: 每日建议从纯文本改为结构化返回（items 数组），每项含 title/action_detail(≤2行)/priority/icon，前端按卡片渲染

### Modified Capabilities

- `daily-advice-cache`: 缓存键需包含活跃茬口 ID 列表，茬口变化时缓存失效；缓存内容改为结构化 JSON
- `user-settings`: 新增 `display_name`（用户称呼）字段，Agent 回复时使用

## Impact

- **后端**：新增 `services/farm_context_service.py`、5 个写操作 Skill 文件、修改 `agents/graph.py`（注入摘要）、修改 `prompts/base.j2`（格式约束 + 称呼）、修改 `schemas/agent.py`（结构化返回）
- **API**：`GET /agent/daily` 返回格式从 `{advice: str}` 改为 `{items: [{title, detail, priority, icon}]}`，**BREAKING** 需同步移动端
- **移动端**：AdviceCard 组件从 Markdown 渲染改为卡片列表渲染，每个 item 一张卡片
- **依赖**：无新外部依赖（写操作 Skill 复用现有 skillify 框架）
