## ADDED Requirements

### Requirement: LLM 异步调用
`graph.py` 中的 `_llm_node` SHALL 使用 `async def` 和 `await llm.ainvoke()` 进行异步 LLM 调用，不得阻塞事件循环。

#### Scenario: 并发请求不阻塞
- **WHEN** 两个用户同时发起 chat 请求
- **THEN** 两个请求 SHALL 并行处理，互不等待

#### Scenario: 单次 LLM 调用成功
- **WHEN** `_llm_node` 调用 `await llm.ainvoke()` 且 LLM API 正常响应
- **THEN** 返回结果与同步 `llm.invoke()` 一致

### Requirement: 并发信号量控制
系统 SHALL 使用 `asyncio.Semaphore` 限制同时进行的 LLM 调用数量，最大并发数默认为 5。

#### Scenario: 并发未超限
- **WHEN** 当前有 3 个并发 LLM 调用，Semaphore 上限为 5
- **THEN** 第 4 个请求 SHALL 立即开始执行

#### Scenario: 并发超限排队
- **WHEN** 当前有 5 个并发 LLM 调用，Semaphore 上限为 5
- **THEN** 第 6 个请求 SHALL 等待某个调用完成后才开始执行

### Requirement: 每次请求重新路由
`llm.py` 的 `get_llm()` SHALL 每次返回新的 `ChatOpenAI` 实例，通过 `LLMClientManager` 获取当前最优的 provider/model 组合，不使用全局单例缓存。

#### Scenario: 连续两次调用可能使用不同模型
- **WHEN** `get_llm()` 被连续调用两次，且有多个可用模型
- **THEN** 两次调用可能返回不同 provider/model 的 ChatOpenAI 实例

#### Scenario: graph 每次调用获取新 LLM
- **WHEN** `_llm_node` 执行时
- **THEN** SHALL 通过 `get_llm()` 获取当前 LLM 实例，而非使用缓存的实例
