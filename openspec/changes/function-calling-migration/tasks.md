## 1. 移除 skillify 预路由（agent_service.py）

- [ ] 1.1 删除 `_try_skillify_route()` 函数定义（~38-67 行）
- [ ] 1.2 `chat_with_agent()` 中移除 skillify 预路由分支（skillify_match 判断、只读 skill 直接执行、写操作预路由识别），保留 pending action 确认流程和 LangGraph 调用
- [ ] 1.3 `stream_chat_with_agent()` 中移除 skillify 预路由分支，保留 pending action 和 LangGraph 流式调用
- [ ] 1.4 移除 `agent_service.py` 中仅用于预路由的导入：`get_skill_manager`、`build_skill_context`（保留 `get_langchain_tools` 供 `_execute_skill` 使用）

## 2. 清理 trace 相关

- [ ] 2.1 移除 `agent_service.py` 中 `node_type="routing"` 的 `skillify_route` trace 记录
- [ ] 2.2 确认 `agent.py` 的 `event_generator` 中查询 skills 的 filter 仅用 `node_type in ("skill_call",)` 即可（移除 `"routing"`）

## 3. 保留必要函数

- [ ] 3.1 确认 `_execute_skill()` 保留（被 `_execute_pending_action()` 调用）
- [ ] 3.2 确认 `_execute_pending_action()` 保留且正常工作
- [ ] 3.3 确认 pending action 确认流程（`chat_with_agent` 中的 confirm/cancel/modify 分支）未受影响

## 4. 验证与测试

- [ ] 4.1 ruff lint 通过，无新 error
- [ ] 4.2 语法检查：`agent_service.py`、`agent.py` 可正常 import
- [ ] 4.3 手动测试：发送 "今天天气咋样" → 走 FC 路由 → LLM 返回自然语言天气描述
- [ ] 4.4 手动测试：发送 "你好" → LLM 直接回复，不触发 skill
- [ ] 4.5 手动测试：发送 "记一笔化肥 200 元" → FC 路由 → 写操作拦截 → 确认流程正常
- [ ] 4.6 验证 trace 记录中不再有 `skillify_route` routing 节点
- [ ] 4.7 验证前端 skills 字段仍正常显示已执行的 skill 名称
