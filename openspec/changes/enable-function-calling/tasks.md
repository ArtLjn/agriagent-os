## 1. 配置层变更

- [ ] 1.1 `app/core/config.py` — `AIConfig` 新增 `enable_thinking: bool = False` 字段，`model` 默认值改为 `qwen3.6-flash-2026-04-16`
- [ ] 1.2 `config.yaml` — 更新 `ai.model` 为 `qwen3.6-flash-2026-04-16`，新增 `ai.enable_thinking: false`

## 2. LLM 初始化层

- [ ] 2.1 `app/core/llm.py` — `get_llm()` 读取 `settings.ai.enable_thinking`，通过 `model_kwargs` 传递 `enable_thinking` 参数给 `ChatOpenAI`
- [ ] 2.2 验证 `get_llm()` 全局单例在 `enable_thinking=false` 时正确创建实例

## 3. System Prompt 强化

- [ ] 3.1 `prompts/base.j2` — 在【能力范围】段添加 tool calling 硬约束："禁止凭记忆回答天气、成本、记录、周期等实时数据，必须调用工具获取"
- [ ] 3.2 `app/core/prompt_registry.py` — 更新内置默认 prompt 的 `_DEFAULT_PROMPTS["system_base"]`，保持与 base.j2 一致

## 4. 端到端验证

- [ ] 4.1 编写测试：验证天气查询触发 `get_weather_forecast` tool call
- [ ] 4.2 编写测试：验证成本查询触发 `get_cost_summary` tool call
- [ ] 4.3 编写测试：验证闲聊不触发 tool call，直接返回文本
- [ ] 4.4 编写测试：验证 `enable_thinking` 配置正确传递给 API
