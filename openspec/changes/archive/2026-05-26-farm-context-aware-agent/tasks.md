## 1. 数据库模型

- [ ] 1.1 修改 `cost_records` 表：新增 `record_subtype`、`counterparty`、`due_date`、`settled_at`、`parent_record_id` 字段
- [ ] 1.2 创建 `debt_balances` 视图或模型：用于快速查询未结清债务的剩余金额
- [ ] 1.3 修改 `CropTemplate` 模型/表：确认字段完整性，支持用户自定义（系统预设标记 `is_system=true`）

## 2. 后端 API — 赊账管理

- [ ] 2.1 修改 `schemas/cost.py`：新增 `CostRecordSubtype` 枚举、`DebtRecordCreate` / `DebtRecordResponse` Schema
- [ ] 2.2 修改 `services/cost_service.py`：支持 `record_subtype` 过滤，成本统计默认排除未结清赊账
- [ ] 2.3 新增 `api/debt.py`：`GET /debts`（支持 status/counterparty 筛选）、`POST /debts/{id}/settle`（还款/收款）
- [ ] 2.4 修改 `api/cost.py`：`POST /costs` 支持 `record_subtype`、`counterparty`、`due_date` 字段

## 3. 后端 API — 多茬口感知

- [ ] 3.1 确认/完善 `services/cycle_service.py`：`get_active_cycles(farm_id)` 方法（如已存在需确认签名和返回值）
- [ ] 3.2 确认/完善 `api/agent.py`：`GET /agent/daily` 在无 `cycle_id` 时按 active 茬口分别生成建议
- [ ] 3.3 修改 `services/advice_cache_service.py`：缓存键包含活跃茬口 ID 列表，茬口变化时缓存失效

## 4. 后端 API — 作物模板管理

- [ ] 4.1 新增 `api/crop.py`：`POST /crops/templates`（创建自定义模板）、`PUT /crops/templates/{id}`、`DELETE /crops/templates/{id}`
- [ ] 4.2 修改 `services/crop_service.py`：支持自定义模板的 CRUD，系统预设模板标记为 `is_system=true`
- [ ] 4.3 修改 `seed_default_farm`：新农场自动创建西瓜和豆角预设模板

## 5. 移动端改造

- [ ] 5.1 记账页面：增加"赊账"类型选择（direct/debt/receivable），显示对方名称和约定还款日字段
- [ ] 5.2 新增"赊账管理"页面：列表展示所有赊账，支持筛选和还款操作
- [ ] 5.3 新增"作物模板管理"页面：创建、编辑、删除自定义作物模板
- [ ] 5.4 首页：增加赊账待还/待收金额的快速展示入口

## 6. 测试

- [ ] 6.1 单元测试：`cost_service` 成本统计排除未结清赊账
- [ ] 6.2 单元测试：`farm_context_service.build_farm_context_summary()` 摘要组装和长度控制（已存在，需确认覆盖率）
- [ ] 6.3 集成测试：`POST /costs` 创建赊账记录 + `POST /debts/{id}/settle` 还款流程
- [ ] 6.4 集成测试：`GET /agent/daily` 无 cycle_id 模式返回多作物建议
- [ ] 6.5 集成测试：缓存键包含活跃茬口列表，茬口变化时缓存失效

## 7. 集成验证

- [ ] 7.1 本地启动后端，验证所有 API 正常
- [ ] 7.2 移动端连接本地后端，测试赊账录入和还款
- [ ] 7.3 验证多作物建议卡片正确展示
- [ ] 7.4 ruff check + ruff format 通过
