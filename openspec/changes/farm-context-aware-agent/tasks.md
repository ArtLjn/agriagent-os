## 1. 数据库模型

- [ ] 1.1 修改 `cost_records` 表：新增 `record_subtype`、`counterparty`、`due_date`、`settled_at`、`parent_record_id` 字段
- [ ] 1.2 创建 `debt_balances` 视图或模型：用于快速查询未结清债务的剩余金额
- [ ] 1.3 修改 `CropCycle` 模型：确保 `status` 字段支持自动计算（保留 `paused` 手动覆盖）
- [ ] 1.4 确认 `CropTemplate` 模型支持用户自定义创建（已存在，需确认字段完整性）

## 2. 后端 API — 赊账管理

- [ ] 2.1 修改 `schemas/cost.py`：新增 `CostRecordSubtype` 枚举、`DebtRecordCreate` / `DebtRecordResponse` Schema
- [ ] 2.2 修改 `services/cost_service.py`：支持 `record_subtype` 过滤，成本统计默认排除未结清赊账
- [ ] 2.3 新增 `api/debt.py`：`GET /debts`（支持 status/counterparty 筛选）、`POST /debts/{id}/settle`（还款/收款）
- [ ] 2.4 修改 `api/cost.py`：`POST /costs` 支持 `record_subtype`、`counterparty`、`due_date` 字段

## 3. 后端 API — 多茬口感知

- [ ] 3.1 修改 `services/cycle_service.py`：新增 `get_active_cycles(farm_id)` 方法，支持自动状态计算
- [ ] 3.2 修改 `api/cycle.py`：`GET /cycles` 支持 `status` 查询参数
- [ ] 3.3 修改 `cycle_service.py`：`advance_stage` 和 `update_stage` 时自动重新计算 `is_current`

## 4. 后端 API — 作物模板管理

- [ ] 4.1 修改 `api/crop.py`：新增 `POST /crops/templates`（创建自定义模板）、`PUT /crops/templates/{id}`、`DELETE /crops/templates/{id}`
- [ ] 4.2 修改 `services/crop_service.py`（或创建）：支持自定义模板的 CRUD，系统预设模板标记为 `is_system=true`
- [ ] 4.3 修改 `seed_default_farm`：新农场自动创建西瓜和豆角预设模板

## 5. Agent 上下文注入

- [ ] 5.1 创建 `services/farm_context_service.py`：`build_farm_context_summary(db, farm_id)` 函数
- [ ] 5.2 上下文摘要组装逻辑：查询 active cycles、近期 logs、月度成本、未结清 debts、未来天气
- [ ] 5.3 摘要长度控制：活跃茬口 ≤2、农事记录 ≤3、债务 ≤3、天气 3 天，总长度 ≤500 字
- [ ] 5.4 修改 `services/agent_service.py`：`get_daily_advice` 和 `chat_with_agent` 调用前注入上下文摘要
- [ ] 5.5 修改 `prompts/base.j2`：新增 `{{ farm_context_summary }}` 占位符（依赖 prompt-governance 完成后接入）

## 6. 每日建议改造

- [ ] 6.1 修改 `api/agent.py`：`GET /agent/daily` 支持无 `cycle_id` 模式，查询所有 active cycles
- [ ] 6.2 修改 `services/agent_service.py`：多茬口建议生成（一次 LLM 调用生成所有 active 茬口建议）
- [ ] 6.3 修改 `services/agent_service.py`：缓存键包含活跃茬口 ID 列表
- [ ] 6.4 修改 `services/advice_cache_service.py`：支持多作物建议的缓存存储和读取

## 7. 移动端改造

- [ ] 7.1 记账页面：增加"赊账"类型选择，显示对方名称和约定还款日字段
- [ ] 7.2 新增"赊账管理"页面：列表展示所有赊账，支持筛选和还款操作
- [ ] 7.3 每日建议页面：改造为卡片布局，每个 active 茬口一个卡片
- [ ] 7.4 新增"作物模板管理"页面：创建、编辑、删除自定义作物模板
- [ ] 7.5 设置页面：新增"关注茬口"、"赊账提醒"开关
- [ ] 7.6 首页：增加赊账待还/待收金额的快速展示入口

## 8. 测试

- [ ] 8.1 单元测试：`cycle_service.get_active_cycles()` 自动状态计算（active/upcoming/completed/paused）
- [ ] 8.2 单元测试：`cost_service` 成本统计排除未结清赊账
- [ ] 8.3 单元测试：`farm_context_service.build_farm_context_summary()` 摘要组装和长度控制
- [ ] 8.4 集成测试：`POST /costs` 创建赊账记录 + `POST /debts/{id}/settle` 还款流程
- [ ] 8.5 集成测试：`GET /agent/daily` 无 cycle_id 模式返回多作物建议
- [ ] 8.6 集成测试：缓存键包含活跃茬口列表，茬口变化时缓存失效

## 9. 集成验证

- [ ] 9.1 本地启动后端，验证所有 API 正常
- [ ] 9.2 移动端连接本地后端，测试赊账录入和还款
- [ ] 9.3 验证多作物建议卡片正确展示
- [ ] 9.4 验证上下文摘要注入后 Agent 回复更精准
- [ ] 9.5 ruff check + ruff format 通过
