## 1. 优化 Python Skill description

- [ ] 1.1 优化 `get_cost_summary`（cost-summary）的 description，补充"余额"、"花了多少"、"赚了多少"、"账"等口语词
- [ ] 1.2 优化 `get_cost_analytics`（cost-analytics）的 description，使用意图场景描述格式
- [ ] 1.3 优化 `create_crop_cycle`（create-crop-cycle）的 description，补充"创建"、"种植"、"春茬"、"秋茬"等触发词
- [ ] 1.4 优化 `create_cost_record`（create-cost-record）的 description，使用意图场景描述格式
- [ ] 1.5 优化 `weather`（weather）的 description，使用意图场景描述格式
- [ ] 1.6 优化 `get_crop_cycle_info`（crop-cycle）的 description，补充"茬口状态"、"当前阶段"等
- [ ] 1.7 优化 `get_recent_farm_logs`（farm-logs）的 description，使用意图场景描述格式
- [ ] 1.8 优化 `log_farm_activity`（log-farm-activity）的 description，使用意图场景描述格式
- [ ] 1.9 优化 `update_crop_stage`（update-crop-stage）的 description，使用意图场景描述格式
- [ ] 1.10 优化 `settle_debt`（settle-debt）的 description，使用意图场景描述格式

## 2. 优化 System Prompt

- [ ] 2.1 在 `backend/prompts/base.j2` 的【工具调用规则】段落中新增【可用工具】映射表，列出所有 10 个 tool 名称与意图关键词

## 3. 更新测试

- [ ] 3.1 更新各 skill 测试文件中 `test_description_contains_trigger_words` 测试用例，匹配新的 description 关键词
- [ ] 3.2 运行全量测试确保无回归

## 4. 验证

- [ ] 4.1 ruff 检查通过
- [ ] 4.2 全量测试通过
- [ ] 4.3 手动验证"我的余额"触发 get_cost_summary tool call
- [ ] 4.4 手动验证"帮我创建春茬种植西瓜"触发 create_crop_cycle tool call
