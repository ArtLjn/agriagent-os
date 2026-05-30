## 1. Prompt 格式引导

- [ ] 1.1 在 `backend/prompts/base.j2` 新增【回复风格】段落，要求 LLM 使用 emoji 前缀（🌱💡⚠️📊💰）、Markdown 列表/加粗组织内容、保持口语化短句

## 2. 天气预报格式化

- [ ] 2.1 重写 `backend/app/agent/skills/weather/scripts/main.py` 的回复格式：`📍 {地点}` + Markdown 表格（日期/天气emoji/温度/降水）+ 预警
- [ ] 2.2 天气数据只展示未来 3 天（非 7 天），日期格式 `M/D`
- [ ] 2.3 添加天气 emoji 映射函数（根据降水/温度选择 ☀️🌤️🌧️ 等）

## 3. Pending action 确认文案

- [ ] 3.1 在 `backend/app/infra/pending_actions.py` 的 `build_confirm_message` 中为每个 WRITE_SKILL 添加 emoji 前缀和可读参数格式映射
- [ ] 3.2 参数映射规则：`crop_name` → 直接显示、`amount+category` → "分类 金额元"、`season+crop_name` → "作物·季节"

## 4. 茬口创建结果格式化

- [ ] 4.1 重写 `backend/app/agent/skills/create-crop-cycle/scripts/main.py` 的 `_format_reply`：✅ emoji 开头 + 有序列表展示阶段（含日期范围 M/D 格式和天数）
- [ ] 4.2 重写 `backend/app/agent/skills/create-crop-template/scripts/main.py` 的成功回复：📋 emoji + 有序列表展示阶段

## 5. 记账成功回复格式化

- [ ] 5.1 重写 `backend/app/agent/skills/create-cost-record/scripts/main.py` 的 `_format_reply`：💰 emoji 开头 + 加粗分类和金额

## 6. 测试验证

- [ ] 6.1 更新 `backend/tests/test_tool_selector.py` 中受影响的断言
- [ ] 6.2 手动测试：天气查询、记账确认、茬口创建在手机端渲染效果
