## 1. 错误分类增强

- [ ] 1.1 `ErrorLevel` 枚举新增 `QUOTA_EXHAUSTED` 值
- [ ] 1.2 `classify_error()` 识别 `AllocationQuota.FreeTierOnly` 错误码，返回 `QUOTA_EXHAUSTED`
- [ ] 1.3 `record_failure()` 对 `QUOTA_EXHAUSTED` 级别直接设 DEAD 状态（需要修改签名传入 error_level 或在内部判断）

## 2. 双模型路由

- [ ] 2.1 `ModelConfig` dataclass 新增 `roles: list[str]` 字段，默认 `["all"]`
- [ ] 2.2 `LLMClientManager._load_config()` 解析 `providers.json` 中的 `roles` 字段
- [ ] 2.3 `LLMClientManager.get_chat_model()` 新增 `role: str = "generation"` 参数，筛选匹配角色的模型
- [ ] 2.4 `get_llm()` 新增 `role: str = "generation"` 参数，透传给 `manager.get_chat_model(role=...)`
- [ ] 2.5 `providers.json` 中为现有模型添加 `roles` 字段（gemma3:12b → tool-selection，gemma4:31b → generation，glm-4.7 → all）

## 3. 请求内重试

- [ ] 3.1 `AIConfig` 新增 `failover_max_retries: int = 3` 字段
- [ ] 3.2 `_llm_node` 的 `ainvoke` 调用改为重试循环：失败时 `get_llm()` 获取新 provider，记录失败，重试
- [ ] 3.3 每次重试记录日志（attempt、provider、model、error_type、latency_ms）
- [ ] 3.4 非可恢复错误（400、schema 错误）不重试，直接抛出

## 4. LLMIntentClassifier 使用轻量模型

- [ ] 4.1 `_get_classifier()` 使用 `manager.get_chat_model(role="tool-selection")` 获取轻量模型
- [ ] 4.2 `_get_classifier()` 的 `LLMIntentClassifier` 构造使用轻量模型的 api_key/base_url/model

## 5. _llm_node 双阶段模型

- [ ] 5.1 首次 LLM 调用（工具选择）使用 `get_llm(role="tool-selection")`
- [ ] 5.2 工具执行后的第二次 LLM 调用（回复生成）使用 `get_llm(role="generation")`

## 6. 测试

- [ ] 6.1 测试：`classify_error()` 对 `AllocationQuota.FreeTierOnly` 返回 `QUOTA_EXHAUSTED`
- [ ] 6.2 测试：`record_failure()` 对 `QUOTA_EXHAUSTED` 直接设 DEAD
- [ ] 6.3 测试：`get_chat_model(role="tool-selection")` 只返回匹配角色的模型
- [ ] 6.4 测试：无 `roles` 字段的模型默认可用于所有角色
- [ ] 6.5 测试：请求内重试 — 首次失败 + 第二次成功 → 返回正常结果
- [ ] 6.6 测试：请求内重试 — 全部失败 → 抛出异常
- [ ] 6.7 手动验证：发送请求触发 403，确认自动切换 provider 并成功返回
