## 1. _llm_node 三路分支

- [ ] 1.1 在 `_llm_node` 开头将 messages 中的 ToolMessage 分为 `pending` 和 `normal` 两组
- [ ] 1.2 实现混合分支：拼接 normal ToolMessage 内容摘要（截取 300 字符）+ pending 确认文案，返回合并后的 AIMessage，不调用 LLM
- [ ] 1.3 保留纯 pending 和纯 normal 分支不变

## 2. 确认文案可读性优化

- [ ] 2.1 在 `pending_actions.py` 的 `build_confirm_message` 中添加参数名到中文显示名的映射（crop_name→作物, amount→金额, category→分类, season→季节, start_date→开始日期 等）
- [ ] 2.2 对 `create_cost_record` 类型的参数做特殊格式化（"化肥 50元" 而非 "category=化肥, amount=50"）
- [ ] 2.3 对 `create_crop_cycle` 类型的参数做特殊格式化（"玉米、春季" 而非 "crop_name=玉米, season=春季"）

## 3. 测试

- [ ] 3.1 添加单元测试：混合 ToolMessage 时 `_llm_node` 返回合并内容
- [ ] 3.2 添加单元测试：纯 pending / 纯 normal 分支不受影响
- [ ] 3.3 添加单元测试：`build_confirm_message` 参数可读性映射
- [ ] 3.4 端到端测试：多意图消息触发 query + write，验证回复包含两部分内容且 pending_action SSE 事件正常发出
