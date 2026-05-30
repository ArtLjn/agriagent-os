## Why

当前 LLM 调用链路存在三个阻塞生产可用的问题：(1) graph.py 中 `_llm_node` 使用同步 `llm.invoke()` 阻塞事件循环，3-4 用户并发时请求排队；(2) 所有请求路由到同一个模型/API key，无法分散负载；(3) cooldown 上限 24h 后会重试已死模型，无限循环。项目即将面向 3-4 个真实用户，需要先解决这些问题。

## What Changes

- **消除 LLM 调用阻塞**：`_llm_node` 改用 `await llm.ainvoke()` + `asyncio.Semaphore` 控制并发上限
- **轮询负载均衡**：`_get_first_available()` 改为 round-robin，请求分散到多个 provider/model 组合
- **去掉 LLM_INSTANCE 单例缓存**：每次请求重新路由，才能实现负载均衡
- **分级熔断**：连续失败 10 次的模型标记 DEAD 永久跳过，provider 级别联动熔断
- **手动开关**：providers.json 支持 `enabled: false` 禁用指定 provider 或 model

## Capabilities

### New Capabilities
- `llm-load-balance`：多 Provider 轮询负载均衡、分级熔断、手动开关
- `llm-async-concurrency`：LLM 异步调用改造、并发信号量控制

### Modified Capabilities

## Impact

- `app/core/llm_client_manager.py` — 路由逻辑从优先级选择改为轮询，新增分级熔断和 enabled 字段
- `app/agent/graph.py` — `_llm_node` 改为 async，使用 ainvoke
- `app/agent/llm.py` — 去掉 LLM_INSTANCE 全局单例缓存，get_llm() 每次返回新实例
- `providers.json` — 新增 enabled 字段（向后兼容，默认 true）
- `tests/test_llm_client_manager.py` — 新增轮询、熔断、并发相关测试
- `tests/test_llm.py` — 适配 get_llm() 不再缓存的行为
