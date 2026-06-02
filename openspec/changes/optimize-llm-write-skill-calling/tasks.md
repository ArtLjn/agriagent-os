## 1. Schema 约束与动态 Enum

- [ ] 1.1 修改 `skills_to_langchain_tools`：为 `category` 字段注入动态 enum（从 `cost_categories` 表加载）
- [ ] 1.2 实现标签缓存机制：加载后缓存，标签 CRUD 时清除缓存
- [ ] 1.3 无标签时的默认 enum 回退：["化肥", "种子", "农药", "人工", "其他"]
- [ ] 1.4 测试：验证 LLM 对"复合肥"选择最接近的现有标签"化肥"

## 2. Pydantic 参数校验与自纠错

- [ ] 2.1 在 `_parallel_tool_node` 中增加 Pydantic 参数校验逻辑
- [ ] 2.2 校验失败时返回包含错误信息的 `ToolMessage`
- [ ] 2.3 测试：验证缺少 `amount` 时不生成 pending action，LLM 自动修正
- [ ] 2.4 测试：验证 `amount="两百"` 时返回类型错误，LLM 修正为数字

## 3. Plan-Then-Execute 增强

- [ ] 3.1 修改 `build_confirm_message`：增加"原话理解"和"提取参数"展示
- [ ] 3.2 新增 `_build_context_message` 方法构建三层确认消息
- [ ] 3.3 修改 `PendingAction` dataclass：增加 `context` 字段（original_input, extracted_params, notes）
- [ ] 3.4 修改 `PendingActionResponse` API schema：前端可展示完整上下文
- [ ] 3.5 测试：验证确认消息包含理解/参数/操作三层信息

## 4. 意图路由（When2Tool）

- [ ] 4.1 实现 `_classify_intent` 函数：基于规则匹配问候/查询/写操作
- [ ] 4.2 在 `invoke_advisor` / `stream_advisor` 入口增加路由判断
- [ ] 4.3 问候语直接回复，不走 LangGraph
- [ ] 4.4 测试：验证"你好"直接回复，"记一笔账"走完整流程

## 5. 前端适配

- [ ] 5.1 修改 pending action 展示组件：展示 `context.original_input` 和 `context.extracted_params`
- [ ] 5.2 新增"最接近匹配提示"UI：当分类被匹配到最接近标签时展示提示
- [ ] 5.3 测试：验证前端正确展示三层确认信息

## 6. 集成验证

- [ ] 6.1 端到端测试："买了200块复合肥" → 匹配"化肥" → 确认消息展示提示
- [ ] 6.2 端到端测试："记一笔账"（缺金额）→ Pydantic 校验失败 → LLM 自纠错 → 正常 pending
- [ ] 6.3 端到端测试："你好" → 直接回复，无 tool call
- [ ] 6.4 回归测试：确保已有功能（TC-WRITE-001 等）不受影响的正常工作
