## 1. 加权路由与分级熔断（llm_client_manager.py）

- [ ] 1.1 ProviderConfig 和 ModelConfig 新增 `weight` 和 `enabled` 字段，`_load_config` 解析这两个字段，向后兼容（weight 缺省 1，enabled 缺省 true）
- [ ] 1.2 新增 `CircuitState` 枚举（COOLING/WARMING/DEAD），重构 `CooldownEntry` 为 `CircuitEntry`，包含 state 字段
- [ ] 1.3 重构 `record_failure()`：根据失败次数自动升级状态（1-3→COOLING, 4-9→WARMING, ≥10→DEAD），DEAD 状态永久跳过
- [ ] 1.4 新增 `_is_provider_healthy()` 方法：统计 provider 下 WARMING/DEAD 模型占比，≥50% 返回 false
- [ ] 1.5 重构 `_get_first_available()` → `_get_next_available()`：过滤 disabled/cooldown/DEAD/不健康 provider，在可用模型中按 provider weight 加权随机选择
- [ ] 1.6 新增 `_weighted_random_choice()` 私有方法：输入 `[(provider, model, api_key, weight)]`，按权重随机返回一个
- [ ] 1.7 更新 `get_chat_model()`、`get_sync_client()`、`get_async_client()`、`get_model_info()` 使用 `_get_next_available()`
- [ ] 1.8 更新 `reload()` 方法：重置 DEAD 状态，重新加载 enabled/weight 配置

## 2. 异步调用与并发控制（graph.py + llm.py）

- [ ] 2.1 `llm.py` 去掉 `LLM_INSTANCE` 全局单例缓存，`get_llm()` 每次通过 Manager 获取新的 ChatOpenAI 实例
- [ ] 2.2 `graph.py` 的 `_llm_node` 改为 `async def`，使用 `await llm.ainvoke()` 替代同步 `llm.invoke()`
- [ ] 2.3 新增模块级 `asyncio.Semaphore(5)` 信号量，`_llm_node` 中 `async with semaphore` 包裹 LLM 调用
- [ ] 2.4 `_llm_node` 内部调用 `get_llm()` 获取当前 LLM 实例而非使用闭包缓存的实例

## 3. providers.json 更新

- [ ] 3.1 为每个 provider 添加 `weight` 字段（ollama: 8, nvidia: 2, dashscope: 1）
- [ ] 3.2 为每个 provider 和 model 添加 `enabled` 字段（全部 true）

## 4. 测试

- [ ] 4.1 新增 `test_weighted_routing`：验证加权随机路由的概率分布（多次调用统计分布）
- [ ] 4.2 新增 `test_circuit_state_upgrade`：验证 COOLING→WARMING→DEAD 状态升级
- [ ] 4.3 新增 `test_dead_permanent_skip`：验证 DEAD 状态模型被永久跳过
- [ ] 4.4 新增 `test_provider_level_circuit`：验证 ≥50% 模型故障时整个 provider 被跳过
- [ ] 4.5 新增 `test_enabled_field`：验证 `enabled: false` 的 provider 和 model 被跳过
- [ ] 4.6 更新 `test_llm.py`：适配 `get_llm()` 不再缓存的行为
- [ ] 4.7 运行全量测试确认无回归
