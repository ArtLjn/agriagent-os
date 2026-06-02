## Why

LLM 调用 403（配额耗尽）时，当前请求直接失败返回"服务不可用"，虽有 `record_failure` 记录 cooldown，但不会在请求内重试下一个 provider。同时所有 LLM 调用（工具选择 + 回复生成）都使用同一模型（如 gemma4:31b），工具选择阶段无需 31B 参数模型，导致首次 LLM 调用耗时 16.9s 严重拖慢整体响应。

## What Changes

- **请求内 LLM 重试**：`_llm_node` 中 LLM 调用失败时，自动切换到下一个可用 provider 重试，最多重试 N 次（可配置），而非直接抛异常给用户
- **403 配额耗尽即时 DEAD**：`classify_error` 对 `AllocationQuota.FreeTierOnly` 类 403 错误直接标记 DEAD（跳过指数退避），避免反复尝试已耗尽的 provider
- **双模型路由**：`LLMClientManager` 支持按用途（tool-selection / generation）选择不同模型，工具选择阶段优先使用轻量模型（如 gemma3:12b），回复生成使用高质量模型
- **LLMIntentClassifier 独立模型**：intent classifier 使用 `get_sync_client()` 时指定轻量模型，避免用 31B 模型做简单的意图分类

## Capabilities

### New Capabilities
- `llm-in-request-retry`: LLM 调用失败时在请求内自动切换 provider 重试，对用户透明
- `llm-fast-tool-router`: 工具选择阶段使用轻量模型（~12B），回复生成使用高质量模型，降低首 token 延迟

### Modified Capabilities
- `llm-circuit-breaker`: 403 配额耗尽错误直接标记 DEAD，不走指数退避

## Impact

- **后端代码**: `app/agent/graph.py`（重试逻辑）、`app/core/llm_client_manager.py`（双模型路由、错误分类增强）、`app/agent/llm.py`（支持指定用途获取模型）
- **配置**: `providers.json` 需要新增 `roles` 字段标记模型适合的用途（tool-selection / generation / all）
- **依赖**: 无新增依赖
- **兼容性**: 现有 providers.json 无 roles 字段时，所有模型默认可用于所有用途
