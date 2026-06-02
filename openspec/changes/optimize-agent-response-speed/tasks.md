## 1. 确认语模板化（跳过第二轮 LLM）

- [ ] 1.1 修改 `_parallel_tool_node`：write skill 拦截后，ToolMessage 直接包含完整确认语
- [ ] 1.2 修改 system prompt： instruct LLM "当 tool 返回 PENDING_MARKER 时，直接展示给用户，不要重写"
- [ ] 1.3 验证：写操作只调用 1 次 LLM，不再走第二轮
- [ ] 1.4 测试：记账延迟从 4-6s 降到 2s 以内

## 2. System Prompt 缓存

- [ ] 2.1 在 `prompt_composer.render()` 加 `lru_cache`，key 为 `farm_id + date + template_name`
- [ ] 2.2 缓存 TTL 设为 1 小时
- [ ] 2.3 farm 信息修改时提供缓存清除接口
- [ ] 2.4 测试：同 farm 同一天第二次请求 system prompt 渲染时间 < 10ms

## 3. 模型路由

- [ ] 3.1 在 `advisor.py` 入口加规则路由：greetings 走轻量模型
- [ ] 3.2 扩展 `llm_client_manager` 支持按 role 获取不同模型（lightweight/standard/premium）
- [ ] 3.3 配置 `config.yaml` 增加轻量模型配置项
- [ ] 3.4 测试："你好"响应延迟 < 1s

## 4. 并行预加载

- [ ] 4.1 在 graph entry 用 `asyncio.gather` 并行启动 LLM + 上下文预加载
- [ ] 4.2 预加载内容：最近成本、当前天气、活跃茬口
- [ ] 4.3 预加载超时 2s，失败不影响主流程
- [ ] 4.4 测试：tool 执行时数据已就绪

## 5. 高频查询缓存

- [ ] 5.1 实现内存缓存（`functools.lru_cache` 或 `cachetools.TTLCache`）
- [ ] 5.2 缓存键：`query_type + farm_id`
- [ ] 5.3 TTL：天气 10 分钟，成本汇总 5 分钟
- [ ] 5.4 写操作后自动失效相关缓存
- [ ] 5.5 测试：第二次天气查询延迟 < 200ms

## 6. 集成验证

- [ ] 6.1 端到端测试："买化肥200" → 1 次 LLM → 2s 内首字
- [ ] 6.2 端到端测试："你好" → 轻量模型 → 1s 内回复
- [ ] 6.3 端到端测试：天气查询 → 第二次命中缓存
- [ ] 6.4 回归测试：确认所有现有功能正常工作
