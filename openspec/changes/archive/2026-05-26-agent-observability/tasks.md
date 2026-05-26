## 1. AgentTrace 写入基础设施

- [ ] 1.1 创建 `app/core/trace.py` 模块，实现 `write_trace()` 函数：接收 farm_id、session_id、node_type、node_name 等参数，使用 SessionLocal 写入 agent_traces 表，包含 input_summary/output_summary 截断到 500 字符、duration_ms 计算、error_message 记录
- [ ] 1.2 为 `write_trace()` 编写单元测试 `tests/test_trace.py`：覆盖正常写入、截断、异常时 error_message 记录

## 2. _llm_node 日志增强 + Trace 写入

- [ ] 2.1 修改 `app/agents/graph.py` 的 `_llm_node`：在 LLM 响应后以 INFO 级别记录工具选择决策（tool_calls 名称列表）或直接回复长度（reply_len），包含 model 名称
- [ ] 2.2 修改 `_llm_node`：在 LLM 调用前后计时，调用 `write_trace()` 写入 llm_call 记录，包含 input_summary（用户最后消息前 200 字符）、output_summary（响应前 200 字符或 tool_calls 摘要）
- [ ] 2.3 修改 `_llm_node`：LLM 调用异常时也写入 trace 记录（error_message 字段），然后 re-raise 异常

## 3. Skill 执行日志增强 + Trace 写入

- [ ] 3.1 修改 `app/agents/graph.py` 的 `_parallel_tool_node` 中 `_call_one`：增加耗时计时，INFO 级别记录 `Skill 完成 | name=xxx | duration_ms=N | result=...`
- [ ] 3.2 修改 `_call_one`：成功时调用 `write_trace()` 写入 tool_call 记录；失败时写入带 error_message 的记录
- [ ] 3.3 修改 `_call_one`：写操作 Skill 拦截时也写入 trace 记录（output_summary="已拦截为 pending action"）

## 4. Skill 发现日志

- [ ] 4.1 修改 `app/skills/__init__.py` 的 `get_skill_manager()`：初始化时 INFO 级别记录每个已加载 Skill 的名称和描述
- [ ] 4.2 修改 `_build_registry()`：DEBUG 级别记录每个注册的 Skill 名称

## 5. Prompt 渲染日志

- [ ] 5.1 修改 `app/core/prompt_renderer.py` 的 `render_prompt`：DEBUG 级别记录模板名称、是否命中注册表、渲染变量 key 列表

## 6. Pending Action 生命周期日志

- [ ] 6.1 修改 `app/core/pending_actions.py` 的 `store_pending`：INFO 级别记录 farm_id、action_id、skill 名称
- [ ] 6.2 修改 `get_pending`：超时清理时 WARNING 级别记录 farm_id 和 skill 名称；正常获取时 DEBUG 级别记录
- [ ] 6.3 修改 `remove_pending`：DEBUG 级别记录 farm_id
- [ ] 6.4 修改 `detect_user_intent`：DEBUG 级别记录消息内容和检测结果

## 7. LLM 客户端 + Report Agent 日志

- [ ] 7.1 修改 `app/core/llm.py` 的 `get_llm()`：首次创建实例时 INFO 级别记录 model 和 base_url
- [ ] 7.2 修改 `app/agents/report.py` 的 `generate_cycle_report`：INFO 级别记录报告生成开始（类型、cycle_id）和完成（结果长度、耗时）

## 8. 验证

- [ ] 8.1 运行 `cd /Users/ljn/Documents/demo/explore/backend && ruff check app/` 确保 lint 通过
- [ ] 8.2 运行 `cd /Users/ljn/Documents/demo/explore/backend && python -m pytest tests/ -x -q` 确保全部测试通过
- [ ] 8.3 启动服务并发送请求，验证日志输出包含新增的结构化字段
