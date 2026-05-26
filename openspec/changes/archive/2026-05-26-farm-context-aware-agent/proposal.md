## Why

`farmer-first-agent` 已完成 Agent 层的"农场感知"：prompt 中注入了 `{{ farm_context_summary }}`（茬口、农事、成本、天气），对话式 Skill 支持了"记账/建茬口/记农事/还赊账/更新阶段"。但这些实现停留在**对话层**——赊账靠 note 字段写文本识别，没有结构化数据；作物模板还是系统预设的西瓜+豆角，用户无法自定义；每日建议 API 虽然支持 `cycle_id=None`，但不确定是否真正按多作物分别生成建议。

父母作为真实用户，需要**数据层和展示层**的完整闭环：能独立查看"我欠谁多少钱"、能自己添加辣椒/小瓜的模板、能看到每个作物各自的建议卡片。

## What Changes（剩余工作）

- **结构化赊账数据模型**：`cost_records` 新增 `record_subtype`（direct/debt/receivable）、`counterparty`、`due_date`、`settled_at`、`parent_record_id` 字段，支持真正的赊账生命周期管理。
- **新增 /debts 独立 API**：`GET /debts`（筛选/统计）、`POST /debts/{id}/settle`（还款/收款），替代当前靠 note 文本识别的取巧方案。
- **作物模板自定义**：`POST/PUT/DELETE /crops/templates`，用户可自由创建作物模板（名称、品种、生长阶段定义）。
- **移动端赊账管理页**：独立的"赊账管理"页面，展示所有未结清债务，支持筛选、还款操作。
- **移动端作物模板管理页**：创建、编辑、删除自定义作物模板。
- **每日建议多作物改造**：确认并完善 `/agent/daily` 在无 `cycle_id` 时按 active 茬口分别生成建议的完整逻辑。

## 已完成（farmer-first-agent 已归档）

- `agent-context-injection`: `farm_context_service.py` + `base.j2` 的 `{{ farm_context_summary }}`
- `user-settings`: `display_name` 字段 + Settings API
- 对话式 Skill：记账、建茬口、记农事、还赊账、更新阶段
- 写操作确认机制：pending action 拦截 + 确认/取消/修正
- 移动端：建议卡片、设置页

## Capabilities（剩余）

### New Capabilities

- `debt-management`: 结构化赊账/应收应付（数据模型 + 独立 API + 管理页面）
- `crop-template-management`: 用户自定义作物模板（替代硬编码）
- `multi-cycle-awareness`: 多茬口并行建议生成与展示（后端 + 移动端卡片）

### Modified Capabilities

- `daily-advice-cache`: 缓存键需包含活跃茬口 ID 列表，支持多作物建议缓存

## Impact

- **后端**：`cost_records` 字段扩展、`api/debt.py` 新增、`CropTemplate` CRUD 扩展
- **API**：`/debts` 系列端点、`/crops/templates` CRUD
- **数据库**：`cost_records` 表字段迁移，现有记录 `record_subtype` 默认 `direct`
- **移动端**：记账页增加"赊账"类型、新增"赊账管理"页、新增"作物模板"页
- **Agent Prompt**：无变更（已完成）
