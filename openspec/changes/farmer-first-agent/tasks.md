## 1. farm_context_service — 上下文注入层

- [ ] 1.1 创建 `services/farm_context_service.py`，实现 `build_summary(db, farm_id)` 函数
- [ ] 1.2 实现 active cycles 查询（≤3 个，含名称+阶段+预计采收日）
- [ ] 1.3 实现近期农事查询（≤3 条，最近 3 天）
- [ ] 1.4 实现未结清债务查询（≤3 笔，最近到期）
- [ ] 1.5 实现月度成本汇总查询（1 条金额）
- [ ] 1.6 实现天气数据获取（从 weather skill 缓存或 API 获取未来 3 天）
- [ ] 1.7 实现摘要裁剪逻辑（各类型 ≤3 条，总长度 ≤300 字）
- [ ] 1.8 实现内存缓存（farm_id 为键，5 分钟过期）
- [ ] 1.9 编写单元测试：摘要组装、裁剪规则、缓存命中/失效

## 2. prompt 模板改造 — 格式约束 + 称呼

- [ ] 2.1 修改 `prompts/base.j2`：新增 `{{ farm_context_summary }}` 占位符
- [ ] 2.2 修改 `prompts/base.j2`：新增 `{{ response_format_rules }}` 占位符
- [ ] 2.3 编写 `response_format_rules` 模板内容（短句式、≤5条、口语化、display_name）
- [ ] 2.4 修改 `core/prompt_renderer.py`：新增 `farm_context_summary` 和 `display_name` 变量注入
- [ ] 2.5 修改 `agents/graph.py`：在 `_llm_node` 中调用 `farm_context_service.build_summary()` 并传给 renderer

## 3. 用户称呼 — settings 扩展

- [ ] 3.1 修改 `models/` 相关模型：Farm 或 Settings 表新增 `display_name` 字段（默认值 "农友"）
- [ ] 3.2 修改 `schemas/` 相关 schema：新增 `display_name` 字段
- [ ] 3.3 修改 `api/` 设置端点：支持 GET/PUT display_name
- [ ] 3.4 移动端设置页新增「称呼」输入项

## 4. 每日建议结构化返回

- [ ] 4.1 修改 `schemas/agent.py`：新增 `AdviceItem(title, detail, priority, icon)` 模型
- [ ] 4.2 修改 `schemas/agent.py`：`DailyAdviceResponse.advice: str` 改为 `items: list[AdviceItem]`
- [ ] 4.3 修改 `services/agent_service.py`：`get_daily_advice` 的 prompt 要求 LLM 输出 JSON items
- [ ] 4.4 实现 LLM 输出 JSON 解析 + Pydantic 校验（含 fallback：解析失败时包装为单条 AdviceItem）
- [ ] 4.5 修改 `services/advice_cache_service.py`：缓存内容改为 JSON 序列化，读取时兼容旧格式 fallback
- [ ] 4.6 修改缓存键：包含活跃茬口 ID 列表
- [ ] 4.7 编写单元测试：JSON 解析、fallback、缓存键变更

## 5. 写操作 Skill — 记账（create_cost_record）

- [ ] 5.1 创建 `skills/create-cost-record/` 目录和 `scripts/main.py`
- [ ] 5.2 实现 Skill：接收 (amount, category, record_date, subtype, counterparty, due_date)，调用 cost_service 创建记录
- [ ] 5.3 Pydantic 参数校验：amount 必须 >0，subtype 限定枚举
- [ ] 5.4 通过 skillify 注册为 LangChain StructuredTool
- [ ] 5.5 编写单元测试

## 6. 写操作 Skill — 建茬口（create_crop_cycle）

- [ ] 6.1 创建 `skills/create-crop-cycle/` 目录和 `scripts/main.py`
- [ ] 6.2 实现 Skill：接收 (crop_name, season)，查找模板，创建茬口
- [ ] 6.3 处理无匹配模板场景：返回提示让 Agent 引导用户创建
- [ ] 6.4 通过 skillify 注册
- [ ] 6.5 编写单元测试

## 7. 写操作 Skill — 记农事（log_farm_activity）

- [ ] 7.1 创建 `skills/log-farm-activity/` 目录和 `scripts/main.py`
- [ ] 7.2 实现 Skill：接收 (activities: list[str], date, cycle_id?)，创建农事记录
- [ ] 7.3 多茬口时支持通过 cycle_id 关联
- [ ] 7.4 通过 skillify 注册
- [ ] 7.5 编写单元测试

## 8. 写操作 Skill — 还赊账（settle_debt）

- [ ] 8.1 创建 `skills/settle-debt/` 目录和 `scripts/main.py`
- [ ] 8.2 实现 Skill：接收 (counterparty, amount?)，查找赊账记录，创建还款记录
- [ ] 8.3 支持部分还款和全额还清
- [ ] 8.4 通过 skillify 注册
- [ ] 8.5 编写单元测试

## 9. 写操作 Skill — 更新阶段（update_crop_stage）

- [ ] 9.1 创建 `skills/update-crop-stage/` 目录和 `scripts/main.py`
- [ ] 9.2 实现 Skill：接收 (cycle_id, stage_name)，更新茬口当前阶段
- [ ] 9.3 通过 skillify 注册
- [ ] 9.4 编写单元测试

## 10. 写操作确认机制

- [ ] 10.1 修改 `agents/graph.py`：在 `_llm_node` 中拦截写操作 Skill 的 tool_call，返回确认消息而非直接执行
- [ ] 10.2 实现内存 pending_actions 字典（farm_id → {action_id, skill_name, params, created_at}）
- [ ] 10.3 修改 `services/agent_service.py`：`chat_with_agent` 检测用户消息是否为确认/取消/修正
- [ ] 10.4 确认后执行 pending action，修正后更新参数重新确认
- [ ] 10.5 编写单元测试：确认流程、取消流程、修正流程、超时清理

## 11. 移动端改造

- [ ] 11.1 修改 `AdviceCard` 组件：从 Markdown 渲染改为卡片列表渲染（每 item 一张卡片）
- [ ] 11.2 卡片样式：左侧 icon + title，下方 detail 灰色小字，右上角 priority 标记
- [ ] 11.3 聊天页面：Agent 确认消息显示为特殊气泡（带确认/取消按钮）
- [ ] 11.4 设置页新增「称呼」输入项

## 12. 集成测试

- [ ] 12.1 集成测试：`GET /agent/daily` 返回结构化 items，包含上下文信息
- [ ] 12.2 集成测试：聊天时 Agent 使用 display_name 称呼和短回复格式
- [ ] 12.3 集成测试：对话记账「昨天买了200块化肥」→ 确认 → 创建记录
- [ ] 12.4 集成测试：对话建茬口「帮我建个辣椒茬口」→ 确认 → 创建茬口
- [ ] 12.5 集成测试：茬口变化导致缓存失效
- [ ] 12.6 ruff check + ruff format 通过
