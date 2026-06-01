## 1. 配置层

- [ ] 1.1 在 `app/core/config.py` 的 `AIConfig` 中添加 `parallel_tool_calls: bool = True` 字段
- [ ] 1.2 在 `config.yaml` 中添加 `parallel_tool_calls: true` 配置项（注释说明可关闭）

## 2. LLM 层 — bind_tools 启用并行

- [ ] 2.1 修改 `app/agent/graph.py:246` 的 `bind_tools()` 调用，读取 `settings.ai.parallel_tool_calls` 配置，条件传入 `parallel_tool_calls=True`
- [ ] 2.2 验证 `ChatOpenAI.bind_tools()` 的 `parallel_tool_calls` 参数在 DashScope 兼容接口下透传正确（检查 HTTP request payload）

## 3. Prompt 引导

- [ ] 3.1 在 `backend/prompts/` 中通过 PromptComposer snippet 添加并行调用引导指令（约 80 字）
- [ ] 3.2 验证 system prompt 渲染后包含引导文本，且不破坏现有变量替换

## 4. Trace 增强

- [ ] 4.1 修改 `app/agent/graph.py` 的 `_parallel_tool_node`，在 `asyncio.gather` 完成后记录聚合 trace（`node_type="parallel_batch"`，包含并行数和各 Skill 耗时）
- [ ] 4.2 确保单 Skill 执行时不记录 `parallel_batch` trace（仅 `len(results) > 1` 时记录）

## 5. 测试

- [ ] 5.1 添加测试：`AIConfig.parallel_tool_calls` 默认为 `True`
- [ ] 5.2 添加测试：`bind_tools()` 在 `parallel_tool_calls=True` 时传入正确参数
- [ ] 5.3 添加测试：`bind_tools()` 在 `parallel_tool_calls=False` 时不传该参数
- [ ] 5.4 添加测试：`_parallel_tool_node` 并行执行 2+ Skill 时记录 `parallel_batch` trace
- [ ] 5.5 添加测试：`_parallel_tool_node` 执行 1 个 Skill 时不记录 `parallel_batch` trace
- [ ] 5.6 手动验证：Playground 发送"今天天气怎么样？顺便看看这个月花了多少钱"，确认一次返回多个 tool_calls 并行执行
