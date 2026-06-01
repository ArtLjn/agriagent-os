## Context

当前 `_llm_node` 的 LLM 调用流程：

```
get_llm() → 创建 ChatOpenAI 实例 → llm.ainvoke() → 成功/失败
                                                    │
                                          失败时 record_failure()
                                          但请求直接失败，不重试
```

`LLMClientManager` 已实现：加权随机 provider 选择、指数退避 cooldown、熔断状态（COOLING/WARMING/DEAD）。但所有机制只跨请求生效，请求内无重试。

Provider 配置（providers.json）：
- ollama: gemma4:31b / glm-4.7 / qwen3-next:80b（本地，零网络延迟）
- nvidia: llama-3.1-70b / nemotron-3-super / deepseek-v4-flash / glm-5.1（云端，有网络延迟）
- dashscope: qwen3.6-flash（配额耗尽，403）

关键代码位置：
- `get_llm()`: `llm.py:25-74`，每次创建新实例
- `_llm_node`: `graph.py:243-389`，LLM 调用 + 异常处理
- `_record_llm_failure`: `graph.py:185-198`，记录到 Manager cooldown
- `classify_error`: `llm_client_manager.py:69-86`，错误分级
- `LLMIntentClassifier`: `tool_selector.py:94-167`，使用 `get_sync_client()`

## Goals / Non-Goals

**Goals:**
- LLM 调用失败时，在请求内自动切换 provider 重试（最多 2-3 次），用户无感知
- 工具选择阶段使用轻量模型（如 gemma3:12b），降低首 token 延迟
- 403 配额耗尽错误直接 DEAD，不浪费重试次数

**Non-Goals:**
- 不修改 `_parallel_tool_node` 的执行逻辑
- 不引入新的 LLM provider
- 不实现流式输出的请求内重试（仅 `ainvoke` 阶段重试）
- 不修改 LLMIntentClassifier 的内部实现（仅更换其使用的模型）

## Decisions

### D1: 请求内重试封装在 `_llm_node` 中

**选择**：在 `_llm_node` 的 `llm.ainvoke()` 调用处增加重试循环，失败时重新调用 `get_llm()` 获取新 provider，最多重试 `max_retries` 次。

```python
max_retries = 3
for attempt in range(max_retries):
    raw_llm = get_llm(role="generation")
    circuit_key = _build_circuit_key(raw_llm)
    try:
        response = await llm.ainvoke([system] + messages)
        _record_llm_success(circuit_key)
        break
    except Exception as exc:
        _record_llm_failure(circuit_key, exc)
        if attempt == max_retries - 1:
            raise
        logger.warning("LLM 重试 | attempt=%d | key=%s", attempt + 1, circuit_key)
```

**理由**：重试逻辑封装在调用点，不侵入 `LLMClientManager` 内部。Manager 只负责 provider 选择和 cooldown 管理。

**替代方案**：
- 在 `ChatOpenAI` 的 `max_retries` 中实现：LangChain 的 `max_retries` 是同 provider 同参数重试，不会换 provider。弃用。
- 在 `LLMClientManager.get_chat_model()` 中实现：需要改变 Manager 的接口语义（从"返回一个客户端"变为"执行并重试"），侵入性大。弃用。

### D2: `get_llm()` 支持 `role` 参数选择不同模型

**选择**：`get_llm(role: str = "generation")` 新增 role 参数。`LLMClientManager.get_chat_model(role=...)` 根据角色筛选模型。

providers.json 中模型新增可选 `roles` 字段：
```json
{"id": "gemma3:12b", "roles": ["tool-selection"]},
{"id": "gemma4:31b", "roles": ["generation"]},
{"id": "glm-4.7", "roles": ["all"]}
```

无 `roles` 字段时默认 `["all"]`，保证向后兼容。

**用途映射**：
- `role="tool-selection"`: `LLMIntentClassifier`（tool_selector.py）+ `_llm_node` 的首次工具选择调用
- `role="generation"`: `_llm_node` 的回复生成调用

**理由**：工具选择只需理解用户意图并匹配工具，12B 模型足够且推理速度快 3-5 倍。回复生成需要高质量，用大模型。

**替代方案**：
- 两个独立的 LLM 实例：配置复杂，维护成本高。弃用。
- 只用 `select_tools()` regex/keyword 结果跳过首次 LLM 调用：已实现，但仍有 regex 未覆盖的场景需要 LLM。弃用。

### D3: 403 配额耗尽错误直接标记 DEAD

**选择**：`classify_error()` 新增对 `AllocationQuota.FreeTierOnly` 错误码的识别，返回新的 `ErrorLevel.QUOTA_EXHAUSTED`。`record_failure()` 对此级别直接跳到 DEAD 状态（failures=10 的等效行为）。

**理由**：配额耗尽不是临时故障，指数退避重试只会浪费时间。直接 DEAD 让后续请求跳过该 provider。

**替代方案**：
- 保持指数退避：浪费 2-3 次重试在已知不可恢复的错误上。弃用。

### D4: 重试次数从配置读取

**选择**：在 `AIConfig` 中新增 `failover_max_retries: int = 3`，`_llm_node` 读取该配置。

**理由**：不同部署环境（本地开发 vs 生产）可能需要不同的重试策略。

## Risks / Trade-offs

- **[重试增加请求延迟]** → Mitigation: 最多 3 次，且 403 直接 DEAD 不浪费重试。首次成功则零开销。
- **[重试期间 stream 连接可能超时]** → Mitigation: 重试仅在 `ainvoke` 阶段，不涉及流式输出。SSE 连接有 keep-alive。
- **[双模型增加 providers.json 复杂度]** → Mitigation: `roles` 字段可选，默认 `["all"]`。无 roles 时行为与现在完全一致。
- **[小模型工具选择质量下降]** → Mitigation: `select_tools()` 的 regex/keyword（Layer 1/2）已覆盖 80% 场景，LLM（Layer 3）仅作兜底。12B 模型对简单意图分类足够。
